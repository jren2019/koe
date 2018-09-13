import numpy as np
from django.http import HttpResponse
from django.template.loader import render_to_string

from koe.model_utils import get_or_error
from koe.models import DatabaseAssignment, Segment, Database, DerivedTensorData
from koe.ts_utils import extract_tensor_metadata, write_metadata,\
    bytes_to_ndarray
from root.models import ExtraAttrValue, ExtraAttr

__all__ = ['get_annotators_and_presets', 'get_preset_config']


def _get_annotation_info(database, annotators):
    syls = Segment.objects.filter(audio_file__database=database)
    nsyls = syls.count()

    labelling_levels = ['label', 'label_family', 'label_subfamily']
    labelling_attrs = ExtraAttr.objects.filter(klass=Segment.__name__, name__in=labelling_levels)

    annotation_info = {}

    for annotator in annotators:

        user_annotation = ExtraAttrValue.objects.filter(owner_id__in=syls, user=annotator)
        annotation_info[annotator] = {}

        for labelling_attr in labelling_attrs:
            user_annotation_this_level = user_annotation.filter(attr=labelling_attr)
            if nsyls == 0:
                user_annotation_complete_this_level = 100
            else:
                user_annotation_complete_this_level = user_annotation_this_level.count() / nsyls * 100

            annotation_info[annotator][labelling_attr.name] = user_annotation_complete_this_level
    return annotation_info


def _render_annotation_info(annotation_info, tensors):
    return render_to_string('partials/annotator_dropdown_list_options.html',
                            {'annotation_info': annotation_info, 'tensors': tensors})


def get_annotators_and_presets(request):
    database_id = get_or_error(request.POST, 'database-id')
    database = get_or_error(Database, dict(id=database_id))

    annotators = [x.user for x in DatabaseAssignment.objects.filter(database=database_id)]
    annotation_info = _get_annotation_info(database, annotators)

    tensors = DerivedTensorData.objects.filter(database=database)

    annotation_rendered = _render_annotation_info(annotation_info, tensors)
    preset_rendered = render_to_string('partials/preset_dropdown_list_options.html', {'tensors': tensors})

    return dict(annotation=annotation_rendered, preset=preset_rendered, ntensors=len(tensors))


def get_preset_config(request):
    tensor_id = get_or_error(request.POST, 'preset-id')
    tensor = get_or_error(DerivedTensorData, dict(id=tensor_id))

    selections = dict(
        annotator=tensor.annotator.id,
        features=list(map(int, tensor.features_hash.split('-'))),
        aggregations=list(map(int, tensor.aggregations_hash.split('-'))),
        dimreduce=tensor.dimreduce,
        ndims=tensor.ndims,
    )

    return selections


def get_metadata(request, tensor_name):
    tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))
    full_tensor = tensor.full_tensor

    full_sids_path = full_tensor.get_sids_path()
    sids = bytes_to_ndarray(full_sids_path, np.int32)

    metadata, headers = extract_tensor_metadata(sids, tensor.annotator)
    content = write_metadata(metadata, sids, headers)

    response = HttpResponse()
    response.write(content)
    response['Content-Type'] = 'text/tsv'
    response['Content-Length'] = len(content)
    return response
