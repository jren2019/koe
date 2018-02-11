import hashlib
import sys
from logging import warning

import numpy as np
import pickle
import os

from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_delete
from django.dispatch import receiver

from scipy.cluster.hierarchy import linkage

from koe.utils import base64_to_array, array_to_base64, triu2mat, mat2triu
from root.models import StandardModel, SimpleModel, ExtraAttr, ExtraAttrValue, AutoSetterGetterMixin, User
from root.utils import spect_path, audio_path, history_path, ensure_parent_folder_exists, data_path

PY3 = sys.version_info[0] == 3
if PY3:
    import builtins
else:
    import __builtin__ as builtins

try:
    builtins.profile
except AttributeError:
    builtins.profile = lambda x: x


class NumpyArrayField(models.TextField):
    def __init__(self, *args, **kwargs):
        super(NumpyArrayField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, NumpyArrayField):
            return value

        if value is None:
            return value

        return base64_to_array(value)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return base64_to_array(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        if not isinstance(value, np.ndarray):
            raise TypeError('value must be a numpy array')
        return array_to_base64(value)


class AudioTrack(StandardModel):
    name = models.CharField(max_length=255, unique=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class Individual(StandardModel):
    name = models.CharField(max_length=255)
    gender = models.CharField(max_length=16)

    def __str__(self):
        return self.name


class AudioFile(StandardModel):
    fs = models.IntegerField()
    length = models.IntegerField()
    name = models.CharField(max_length=1024)
    track = models.ForeignKey(AudioTrack, null=True, blank=True, on_delete=models.SET_NULL)
    individual = models.ForeignKey(Individual, null=True, blank=True, on_delete=models.SET_NULL)
    quality = models.CharField(max_length=2, null=True, blank=True)

    @property
    def file_path(self):
        return audio_path(self.name, 'wav')

    @property
    def mp3_path(self):
        return audio_path(self.name, 'mp3')

    def __str__(self):
        return self.name


# Create a nested dictionary from the ClusterNode's returned by SciPy
def add_node(node, idx_2_seg_id, parent, root_triu):
    # First create the new node and append it to its parent's children
    new_node = dict(dist=root_triu - node.dist, children=[])

    idx = node.id
    if idx in idx_2_seg_id:
        new_node['seg-id'] = idx_2_seg_id[idx]

    if 'children' in parent:
        parent["children"].append(new_node)
    else:
        for k in new_node:
            parent[k] = new_node[k]

    # Recursively add the current node's children
    if node.left:
        add_node(node.left, idx_2_seg_id, new_node, root_triu)
    if node.right:
        add_node(node.right, idx_2_seg_id, new_node, root_triu)


def dist_from_root(tree):
    last_idx = tree.shape[0]
    indices = np.ndarray((last_idx + 1,), dtype=np.uint32)
    distances = np.ndarray((last_idx + 1,), dtype=np.float32)
    for i in range(last_idx):
        branch = tree[i, :]
        l1 = int(branch[0])
        l2 = int(branch[1])
        dist = branch[2]
        if l1 <= last_idx:
            indices[l1] = i
            distances[l1] = dist / 2
        if l2 <= last_idx:
            indices[l2] = i
            distances[l2] = dist / 2
    # root_triu = tree[-1, 2] / 2
    return indices, distances


def upgma_triu(segments_ids, dm):
    all_segments_ids = np.array(list(Segment.objects.all().order_by('id').values_list('id', flat=True)))
    chksum = DistanceMatrix.calc_chksum(all_segments_ids)

    if dm is None:
        return [0] * len(segments_ids)
    assert chksum == dm.chksum

    mat_idx = np.searchsorted(all_segments_ids, segments_ids)
    triu = dm.triu
    distmat = triu2mat(triu)
    distmat = distmat[:, mat_idx][mat_idx, :]
    distmat[np.isnan(distmat)] = 0
    triu = mat2triu(distmat)

    tree = linkage(triu, method='average')
    indices, distances = dist_from_root(tree)

    return indices.tolist(), distances.tolist()


class Segment(models.Model, AutoSetterGetterMixin):
    start_time_ms = models.IntegerField()
    end_time_ms = models.IntegerField()

    segmentation = models.ForeignKey('Segmentation', on_delete=models.CASCADE)

    @classmethod
    def bulk_get_segment_info(cls, segs, extras):
        user = extras['user']
        rows = []
        if isinstance(segs, QuerySet):
            attr_values_list = list(segs.values_list('id', 'start_time_ms', 'end_time_ms',
                                                     'segmentation__audio_file__name',
                                                     'segmentation__audio_file__id',
                                                     'segmentation__audio_file__quality',
                                                     'segmentation__audio_file__track__name',
                                                     'segmentation__audio_file__track__date',
                                                     'segmentation__audio_file__individual__name',
                                                     'segmentation__audio_file__individual__gender'))
        else:
            attr_values_list = [(x.id, x.start_time_ms, x.end_time_ms, x.segmentation.audio_file.name,
                                 x.segmentation.audio_file.id) for x in segs]

        segids = [str(x[0]) for x in attr_values_list]
        extra_attrs = ExtraAttr.objects.filter(klass=cls.__name__)
        extra_attr_values_list = ExtraAttrValue.objects\
            .filter(user=user, attr__in=extra_attrs, owner_id__in=segids) \
            .values_list('owner_id', 'attr__name', 'value')

        song_ids = list(set([x[4] for x in attr_values_list]))
        song_extra_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
        song_extra_attr_values_list = ExtraAttrValue.objects\
            .filter(user=user, attr__in=song_extra_attrs, owner_id__in=song_ids) \
            .values_list('owner_id', 'attr__name', 'value')

        extra_attr_values_lookup = {}
        for id, attr, value in extra_attr_values_list:
            if id not in extra_attr_values_lookup:
                extra_attr_values_lookup[id] = {}
            extra_attr_dict = extra_attr_values_lookup[id]
            extra_attr_dict[attr] = value

        song_extra_attr_values_lookup = {}
        for id, attr, value in song_extra_attr_values_list:
            if id not in song_extra_attr_values_lookup:
                song_extra_attr_values_lookup[id] = {}
            extra_attr_dict = song_extra_attr_values_lookup[id]
            extra_attr_dict[attr] = value

        ids = [x[0] for x in attr_values_list]

        dm = extras['dm']
        # dm = DistanceMatrix.objects.filter(id=dm).first()
        dm = None

        nrows = len(attr_values_list)
        if dm is None:
            indices, distances = [0] * nrows, [0] * nrows
        else:
            indices, distances = upgma_triu(ids, dm)

        for i in range(nrows):
            id, start, end, song, song_id, quality, track, date, individual, gender = attr_values_list[i]
            dist = distances[i]
            index = indices[i]
            spect_img = spect_path(str(id))
            duration = end - start
            row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=song, spectrogram=spect_img,
                       distance=dist, dtw_index=index, song_track=track, song_individual=individual, song_gender=gender,
                       song_quality=quality)
            extra_attr_dict = extra_attr_values_lookup.get(str(id), {})
            song_extra_attr_dict = song_extra_attr_values_lookup.get(str(song_id), {})

            for attr in extra_attr_dict:
                row[attr] = extra_attr_dict[attr]

            for song_attr in song_extra_attr_dict:
                attr = 'song_{}'.format(song_attr)
                row[attr] = song_extra_attr_dict[song_attr]

            rows.append(row)

        return rows

    def __str__(self):
        return '{} - {}:{}'.format(self.segmentation.audio_file.name, self.start_time_ms, self.end_time_ms)

    class Meta:
        ordering = ('segmentation', 'start_time_ms')


class Segmentation(StandardModel):
    """
    Represents a segmentation scheme, which aggregate all segments
    """
    audio_file = models.ForeignKey(AudioFile, null=True, on_delete=models.CASCADE)
    source = models.CharField(max_length=1023)

    def get_segment_count(self):
        return Segment.objects.filter(segmentation=self).count()

    def get_segments(self):
        segments = Segment.objects.filter(segmentation=self).order_by('start_time_norm')
        return segments

    def __str__(self):
        return '{} by {}'.format(self.audio_file.name, self.source)


class CompareAlgorithm(StandardModel):
    name = models.CharField(max_length=255)


class DistanceMatrix(StandardModel):
    chksum = models.CharField(max_length=24)
    algorithm = models.ForeignKey(CompareAlgorithm, on_delete=models.CASCADE)

    @classmethod
    def calc_chksum(cls, ids):
        ids_str = ''.join(map(str, ids))
        return hashlib.md5(ids_str.encode('ascii')).hexdigest()[:24]

    def save(self, *args, **kwargs):
        fpath = data_path('pickle', self.chksum)
        ensure_parent_folder_exists(fpath)
        if hasattr(self, '_ids'):
            ids = self._ids
        else:
            ids = self.ids

        if hasattr(self, '_triu'):
            triu = self._triu
        else:
            triu = self.triu

        with open(fpath, 'wb') as f:
            loaded = dict(ids=ids, triu=triu)
            pickle.dump(loaded, f, pickle.HIGHEST_PROTOCOL)

        super(DistanceMatrix, self).save(*args, **kwargs)

    def load(self):
        fpath = data_path('pickle', self.chksum)
        with open(fpath, 'rb') as f:
            loaded = pickle.load(f)
            self._ids = loaded['ids']
            self._triu = loaded['triu']

    @property
    def ids(self):
        if not hasattr(self, '_ids'):
            self.load()
        return self._ids

    @property
    def triu(self):
        if not hasattr(self, '_triu'):
            self.load()
        return self._triu

    @ids.setter
    def ids(self, val):
        self._ids = val

    @triu.setter
    def triu(self, val):
        self._triu = val

    class Meta:
        unique_together = ('chksum', 'algorithm')


class ValueForSorting(StandardModel):
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(CompareAlgorithm, on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        unique_together = ('segment', 'algorithm')


class HistoryEntry(StandardModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time = models.DateTimeField()
    filename = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        self.filename = '{}-{}.zip'.format(self.user.username, self.time.strftime('%Y-%m-%d_%H-%M-%S'))
        super(HistoryEntry, self).save(*args, **kwargs)

    @classmethod
    def get_url(cls, objs, extras):
        """
        :return: a dict with key=id and value=the Markdown-styled url
        """
        if isinstance(objs, QuerySet):
            values_list = objs.values_list('id', 'filename')
        else:
            values_list = [(x.id, x.filename) for x in objs]

        retval = {}

        for id, filename in values_list:
            url = '{}'.format(history_path(filename))
            retval[id] = '[{}]({})'.format(url, filename)

        return retval

    @classmethod
    def get_creator(cls, objs, extras):
        """
        :return: a dict with key=id and value=the Markdown-styled url
        """
        if isinstance(objs, QuerySet):
            values_list = objs.values_list('id', 'user__username')
        else:
            values_list = [(x.id, x.user.username) for x in objs]

        retval = {}

        for id, username in values_list:
            retval[id] = username

        return retval


@receiver(post_delete, sender=HistoryEntry)
def _mymodel_delete(sender, instance, **kwargs):
    filepath = history_path(instance.filename)
    print('Delete {}'.format(filepath))
    if os.path.isfile(filepath):
        os.remove(filepath)
    else:
        warning('File {} doesnot exist.'.format(filepath))

