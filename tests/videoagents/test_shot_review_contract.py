"""The per-shot review transport cannot describe an incomplete review pack."""
import copy

import pytest
from pydantic import ValidationError

from videoagents.contracts import DirectorShotReviewManifest, DirectorShotReviewSpec, ResumeRequest


def manifest_payload():
    def item(index, start, end):
        return {
            'index': index, 'shot_id': f's{index}', 'start_frame': start, 'end_frame': end,
            'review_frame': start + 30, 'component_id': 'evidence', 'set_id': 'A05',
            'component_ids': ['evidence', 'Snapcn-TextReveal'], 'title': 'Read the evidence',
            'body': '', 'asset_src': None, 'source_label': 'Official source', 'narration': 'Current narration.',
            'component_reason': 'Read this source passage.', 'visual_action': 'Show the source and focus on its sentence.',
            'image': {'artifact_id': f'image-{index}', 'kind': 'shot_review_frame', 'name': f'shot-{index}.png',
                      'mime_type': 'image/png', 'size_bytes': 100, 'sha256': str(index) * 64,
                      'url': f'/api/artifacts/image-{index}', 'revision': 2},
        }
    return {
        'schema_version': 1, 'mode': 'per_shot_stills', 'job_id': 'a' * 32, 'revision': 2,
        'director_plan_artifact_id': 'plan', 'director_plan_sha256': 'b' * 64,
        'dependency_fingerprint': 'c' * 64, 'timeline_fingerprint': 'd' * 64,
        'width': 1080, 'height': 1920, 'fps': 30, 'duration_in_frames': 180,
        'items': [item(1, 0, 90), item(2, 90, 180)],
    }


def test_valid_pack_preserves_absolute_frames_and_every_shot():
    value = DirectorShotReviewManifest.model_validate(manifest_payload())
    assert [item.review_frame for item in value.items] == [30, 120]
    assert [item.shot_id for item in value.items] == ['s1', 's2']


@pytest.mark.parametrize('mutation', [
    lambda p: p['items'].pop(),
    lambda p: p['items'][1].update(shot_id='s1'),
    lambda p: p['items'][1].update(start_frame=91),
    lambda p: p['items'][0].update(review_frame=90),
    lambda p: p['items'][1].update(index=1),
    lambda p: p['items'][1].update(image=copy.deepcopy(p['items'][0]['image'])),
    lambda p: p['items'][0]['image'].update(kind='cover'),
    lambda p: p['items'][0]['image'].update(revision=1),
    lambda p: p['items'][0].update(component_ids=['Snapcn-TextReveal']),
])
def test_invalid_or_incomplete_pack_is_rejected(mutation):
    payload = manifest_payload()
    mutation(payload)
    with pytest.raises(ValidationError):
        DirectorShotReviewManifest.model_validate(payload)


def test_each_shot_requires_nonblank_director_explanation():
    with pytest.raises(ValidationError):
        DirectorShotReviewSpec(shot_id='s1', review_frame=30, component_reason=' ', visual_action='Explain')


def test_reviewed_ids_are_explicit_unique_and_only_for_confirm():
    payload = {'base_revision': 2, 'decision': 'confirm', 'note': 'All shots reviewed.',
               'idempotency_key': 'shot-review-confirm', 'pending_token': 'a' * 32}
    assert ResumeRequest(**payload, reviewed_shot_ids=['s1', 's2']).reviewed_shot_ids == ['s1', 's2']
    assert 'reviewed_shot_ids' not in ResumeRequest(**payload).model_dump()
    for ids in ([], ['s1', 's1'], [' ']):
        with pytest.raises(ValidationError):
            ResumeRequest(**payload, reviewed_shot_ids=ids)
    with pytest.raises(ValidationError):
        ResumeRequest(**{**payload, 'decision': 'revise'}, reviewed_shot_ids=['s1'])
