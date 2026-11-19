from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


class FakeDict:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def __setitem__(self, key, value):
        self.values[key] = value

    def put(self, key, value, *, skip_if_exists=False):
        if skip_if_exists and key in self.values:
            return False
        self.values[key] = value
        return True

    def pop(self, key, default=None):
        return self.values.pop(key, default)


class FaceSwapClaimTests(TestCase):
    @patch('ml.modal_faceswap_server.faceswap_job_status', new_callable=FakeDict)
    def test_same_client_job_id_has_one_claim(self, status):
        from ml.modal_faceswap_server import _claim_job

        first = _claim_job('client-1')
        second = _claim_job('client-1')

        self.assertEqual(first, second)
        self.assertEqual(status.values['client:client-1']['job_id'], first)
        self.assertIsNone(status.values[first]['output_s3_key'])

    @patch('ml.modal_faceswap_server.faceswap_job_status', new_callable=FakeDict)
    @patch('ml.modal_faceswap_server.FaceSwapServer')
    def test_spawn_failure_is_retryable_without_second_concurrent_spawn(self, server, status):
        from ml.modal_faceswap_server import _claim_job, _spawn_if_needed

        request = {
            'photo_s3_key': 'faceswap/uploads/photos/a.jpg',
            'video_s3_key': 'faceswap/templates/videos/b.mp4',
            'client_job_id': 'client-2',
        }
        job_id = _claim_job('client-2')
        server.return_value.process.spawn.side_effect = RuntimeError('spawn down')

        with self.assertRaisesRegex(RuntimeError, 'spawn down'):
            _spawn_if_needed(request, job_id)

        self.assertEqual(status.values[job_id]['status'], 'failed')
        self.assertTrue(status.values[job_id]['retryable'])

        server.return_value.process.spawn.side_effect = None
        _spawn_if_needed(request, job_id)
        _spawn_if_needed(request, job_id)
        self.assertEqual(server.return_value.process.spawn.call_count, 2)


class FaceFusionCommandTests(TestCase):
    def test_reference_mode_with_ref_time(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=2.5)

        self.assertIn('reference', cmd)
        frame_index = cmd.index('--reference-frame-number')
        self.assertEqual(cmd[frame_index + 1], '62')
        for token in ('hyperswap_1b_256', 'codeformer', '25', '256x256', 'live_portrait',
                      'occlusion', 'region', 'many'):
            self.assertIn(token, cmd)
        processors = cmd[cmd.index('--processors') + 1:cmd.index('--processors') + 4]
        self.assertEqual(processors, ['face_swapper', 'expression_restorer', 'face_enhancer'])
        self.assertNotIn('--reference-face-distance', cmd)
        self.assertNotIn('large-small', cmd)

    def test_largest_face_mode_without_ref_time(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=None)

        self.assertIn('one', cmd)
        self.assertIn('large-small', cmd)
        self.assertNotIn('--reference-frame-number', cmd)

    def test_progress_mapping(self):
        from ml.modal_faceswap_server import _map_progress

        self.assertEqual([_map_progress(p) for p in (0, 50, 100)], [10, 50, 90])


class FaceSelectionCommandTests(TestCase):
    def test_selected_face_uses_reference_position_and_order(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(
            Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=2.5, face_position=2
        )

        def value(flag):
            return cmd[cmd.index(flag) + 1]

        self.assertEqual(value('--face-selector-mode'), 'reference')
        self.assertEqual(value('--reference-frame-number'), str(round(2.5 * 25)))
        self.assertEqual(value('--face-selector-order'), 'large-small')
        self.assertEqual(value('--reference-face-position'), '2')
        self.assertEqual(cmd.count('--face-selector-mode'), 1)

    def test_selected_frame_number_rounds(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(
            Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=1.23, face_position=0
        )
        self.assertEqual(cmd[cmd.index('--reference-frame-number') + 1], '31')

    def test_without_selection_keeps_previous_reference_command(self):
        from ml.modal_faceswap_server import _facefusion_command

        cmd = _facefusion_command(Path('p.jpg'), Path('v.mp4'), Path('o.mp4'), ref_time_s=2.5)
        self.assertEqual(cmd[cmd.index('--reference-face-position') + 1], '0')
        self.assertNotIn('--face-selector-order', cmd)


class FaceIndexChoiceTests(TestCase):
    # Orden large-small como lo devuelve FaceFusion: [x1, y1, x2, y2].
    BBOXES = [
        [100, 100, 300, 300],  # 0: grande, centro (200, 200)
        [400, 120, 500, 220],  # 1: mediana, centro (450, 170)
        [600, 500, 650, 550],  # 2: chica, centro (625, 525)
    ]

    def test_point_inside_face(self):
        from ml.modal_faceswap_server import _choose_face_index

        self.assertEqual(_choose_face_index(self.BBOXES, (450, 170)), 1)
        self.assertEqual(_choose_face_index(self.BBOXES, (610, 540)), 2)
        self.assertEqual(_choose_face_index(self.BBOXES, (120, 280)), 0)

    def test_overlapping_faces_pick_nearest_center(self):
        from ml.modal_faceswap_server import _choose_face_index

        bboxes = [[0, 0, 200, 200], [150, 150, 250, 250]]
        self.assertEqual(_choose_face_index(bboxes, (190, 190)), 1)

    def test_point_outside_picks_nearest_within_limit(self):
        from ml.modal_faceswap_server import _choose_face_index

        # Fuera de todas; la más cercana es la 1 (centro a 80 px, límite 150 px).
        self.assertEqual(_choose_face_index(self.BBOXES, (450, 250)), 1)

    def test_no_face_near_point(self):
        from ml.modal_faceswap_server import _choose_face_index

        self.assertIsNone(_choose_face_index(self.BBOXES, (1200, 50)))
        self.assertIsNone(_choose_face_index([], (10, 10)))

    def test_point_is_mapped_proportionally(self):
        from ml.modal_faceswap_server import _map_point_to_frame

        self.assertEqual(_map_point_to_frame(0.5, 0.25, 720, 1280), (360.0, 320.0))

    @patch('ml.modal_faceswap_server.detect_reference_faces')
    def test_select_target_face(self, detect):
        from ml.modal_faceswap_server import NO_FACE_AT_POINT, select_target_face

        detect.return_value = {'width': 1000, 'height': 1000, 'bboxes': self.BBOXES}
        self.assertEqual(select_target_face(Path('p'), Path('v'), 1.0, 0.45, 0.17), 1)
        with self.assertRaisesRegex(ValueError, NO_FACE_AT_POINT):
            select_target_face(Path('p'), Path('v'), 1.0, 0.95, 0.05)

    def test_probe_output_is_parsed_from_last_marker(self):
        from ml.modal_faceswap_server import FACE_PROBE_PREFIX, _parse_probe_output

        stdout = 'log\n' + FACE_PROBE_PREFIX + '{"width": 1, "height": 2, "bboxes": []}\n'
        self.assertEqual(_parse_probe_output(stdout), {'width': 1, 'height': 2, 'bboxes': []})
        with self.assertRaises(RuntimeError):
            _parse_probe_output('sin marcador')


class FaceSelectionValidationTests(TestCase):
    def test_accepts_full_or_empty_selection(self):
        from ml.modal_faceswap_server import _validate_selection

        self.assertEqual(_validate_selection({}), (None, None, None))
        self.assertEqual(
            _validate_selection({'ref_time_s': 2, 'face_x': 0.1, 'face_y': 1}), (2.0, 0.1, 1.0)
        )

    def test_rejects_incomplete_or_out_of_range(self):
        from ml.modal_faceswap_server import (
            FACE_POINT_INVALID,
            SELECTION_INCOMPLETE,
            _validate_selection,
        )

        for request in (
            {'face_x': 0.5, 'face_y': 0.5},
            {'ref_time_s': 1, 'face_x': 0.5},
        ):
            with self.assertRaisesRegex(ValueError, SELECTION_INCOMPLETE):
                _validate_selection(request)
        for request in (
            {'ref_time_s': 1, 'face_x': 1.5, 'face_y': 0.5},
            {'ref_time_s': 1, 'face_x': True, 'face_y': 0.5},
            {'ref_time_s': 1, 'face_x': '0.5', 'face_y': 0.5},
        ):
            with self.assertRaisesRegex(ValueError, FACE_POINT_INVALID):
                _validate_selection(request)


class FaceSwapKeyValidationTests(TestCase):
    def test_rejects_invalid_keys(self):
        from ml.modal_faceswap_server import _validate_key

        for key in ('', '/abs', 'a/../b'):
            with self.assertRaises(ValueError):
                _validate_key(key)
        self.assertEqual(_validate_key(' faceswap/a.jpg '), 'faceswap/a.jpg')
