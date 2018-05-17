import os
from django.conf import settings
from django.core.management.base import BaseCommand

from koe.models import Segment, AudioFile
from root.models import ExtraAttrValue


class Command(BaseCommand):
    def handle(self, *args, **options):
        segment_ids = frozenset(Segment.objects.values_list('id', flat=True))
        mask_path = os.path.join(settings.MEDIA_URL, 'spect', 'mask')[1:]

        existing_masks = os.listdir(mask_path)

        for existing_mask in existing_masks:
            existing_mask_id = int(existing_mask[:-4])
            if existing_mask_id not in segment_ids:
                filepath = '{}/{}'.format(mask_path, existing_mask)
                print('File {} is a ghost'.format(filepath))
                os.remove(filepath)

        spect_path = os.path.join(settings.MEDIA_URL, 'spect', 'fft', 'syllable')[1:]

        existing_spects = os.listdir(spect_path)

        for existing_spect in existing_spects:
            existing_spect_id = int(existing_spect[:-4])
            if existing_spect_id not in segment_ids:
                filepath = '{}/{}'.format(spect_path, existing_spect)
                print('File {} is a ghost'.format(filepath))
                os.remove(filepath)

        audio_file_names = frozenset(AudioFile.objects.values_list('name', flat=True))
        wav_path = os.path.join(settings.MEDIA_URL, 'audio', 'wav')[1:]
        existing_wavs = os.listdir(wav_path)
        for existing_wav in existing_wavs:
            if existing_wav not in audio_file_names:
                filepath = '{}/{}'.format(wav_path, existing_wav)
                print('File {} is a ghost'.format(filepath))
                os.remove(filepath)

        compressed_audio_path = os.path.join(settings.MEDIA_URL, 'audio', settings.AUDIO_COMPRESSED_FORMAT)[1:]
        existing_compressed_audios = os.listdir(compressed_audio_path)
        for existing_compressed_audio in existing_compressed_audios:
            name_no_ext, _ = os.path.splitext(existing_compressed_audio)
            existing_compressed_audio_as_wav = '{}.wav'.format(name_no_ext)

            if existing_compressed_audio_as_wav not in audio_file_names:
                filepath = '{}/{}'.format(compressed_audio_path, existing_compressed_audio)
                print('File {} is a ghost'.format(filepath))
                os.remove(filepath)

        ExtraAttrValue.objects.filter(attr__klass=Segment.__name__).exclude(owner_id__in=segment_ids).delete()

        audio_file_ids = frozenset(AudioFile.objects.values_list('id', flat=True))
        ExtraAttrValue.objects.filter(attr__klass=AudioFile.__name__).exclude(owner_id__in=audio_file_ids).delete()