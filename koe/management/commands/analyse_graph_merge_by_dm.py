"""
Start with all syllables belonging to one class, then split them by distance until each syllable is one class.
At each step, produce sequences, construct a graph and extract features from the graph
"""
import pickle

import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial import distance
from scipy.stats import zscore

from koe.cluster_analysis_utils import SimpleNameMerger, Md5NameMerger,\
    get_clustering_based_on_user_annotation
from koe.management.abstract_commands.analyse_graph_merge import AnalyseGraphMergeCommand
from koe.management.utils.prompt_utils import prompt_for_object
from koe.model_utils import get_or_error, natural_order
from koe.models import DataMatrix, Database
from koe.sequence_utils import calc_class_dist_by_syllable_features
from koe.ts_utils import bytes_to_ndarray
from koe.ts_utils import get_rawdata_from_binary
from koe.utils import triu2mat, mat2triu
from root.models import User


def get_dm(dmid):
    if dmid is None:
        databases = Database.objects.filter(id__in=DataMatrix.objects.all().values_list('database', flat=True))
        prompt_for_database = 'Please select a database: (Press Ctrl + C to exit)'
        database = prompt_for_object(prompt_for_database, databases)

        dms = DataMatrix.objects.filter(database=database)
        prompt_for_dm = 'Choose from one of the following datamatrices: (Press Ctrl + C to exit)'
        dm = prompt_for_object(prompt_for_dm, dms)
    else:
        dm = get_or_error(DataMatrix, dict(id=dmid))
    return dm


def drop_useless_columns(mat):
    colmin = np.min(mat, axis=0)
    colmax = np.max(mat, axis=0)

    useful_col_ind = np.where(np.logical_not(np.isclose(colmin, colmax, atol=1e-04)))[0]
    mat = mat[:, useful_col_ind]
    return mat


class Command(AnalyseGraphMergeCommand):
    def get_name_merger_class(self, options):
        annotator_name = options['annotator_name']
        if annotator_name is not None:
            name_merger_class = SimpleNameMerger
        else:
            name_merger_class = Md5NameMerger
        return name_merger_class

    def prepare_data_for_analysis(self, pkl_filename, options):
        label_level = options['label_level']
        cdm = options['cdm']
        dmid = options['dmid']
        annotator_name = options['annotator_name']

        methods = dict(mean=np.mean, median=np.median)
        method = get_or_error(methods, cdm, 'Unknown value {} for --class-distance-method.'.format(cdm))
        dm = get_dm(dmid)
        sids_path = dm.get_sids_path()
        source_bytes_path = dm.get_bytes_path()

        sids = bytes_to_ndarray(sids_path, np.int32)
        coordinates = get_rawdata_from_binary(source_bytes_path, len(sids))
        coordinates = drop_useless_columns(coordinates)
        coordinates = zscore(coordinates)
        coordinates[np.where(np.isinf(coordinates))] = 0
        coordinates[np.where(np.isnan(coordinates))] = 0

        dist_triu = distance.pdist(coordinates, 'euclidean')
        distmat = triu2mat(dist_triu)

        if annotator_name is not None:
            annotator = get_or_error(User, dict(username__iexact=annotator_name))
            unique_labels, enum_labels = get_clustering_based_on_user_annotation(annotator, label_level, sids)
            nlabels = len(unique_labels)
            distmat, classes_info = calc_class_dist_by_syllable_features(enum_labels, nlabels, distmat, method)
            dist_triu = mat2triu(distmat)
        else:
            unique_labels = []
            enum_labels = []
            classes_info = []
            for sind, sid in enumerate(sids):
                label = str(sind)
                unique_labels.append(label)
                enum_labels.append(sind)
                classes_info.append([sind])

        tree = linkage(dist_triu, method='average')
        order = natural_order(tree)
        sorted_order = np.argsort(order).astype(np.int32)

        saved_dict = dict(tree=tree, sorted_order=sorted_order, distmat=distmat, dbid=dm.database.id,
                          sids=sids, coordinates=coordinates, unique_labels=unique_labels, classes_info=classes_info)
        with open(pkl_filename, 'wb') as f:
            pickle.dump(saved_dict, f)

        return saved_dict

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--dm-id', action='store', dest='dmid', required=False, type=str,
                            help='ID of the DM, if not provided the program will ask', )
        parser.add_argument('--annotator', action='store', dest='annotator_name', required=False, type=str,
                            help='Name of the person who owns this database, case insensitive', )
        parser.add_argument('--label-level', action='store', dest='label_level', required=False, type=str,
                            help='Level of labelling to use', )
        parser.add_argument('--class-distance-method', action='store', dest='cdm', default='mean', type=str)