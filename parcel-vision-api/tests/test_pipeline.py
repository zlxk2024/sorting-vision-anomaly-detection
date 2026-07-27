import json
import unittest

import numpy as np

from parcel_vision.demo import make_synthetic_scene
from parcel_vision.generate_scene import make_mixed_scene
from parcel_vision.grasp_plan import build_grasp_plan
from parcel_vision.irregular_scene import make_irregular_scene
from parcel_vision.io import build_protocol_response
from parcel_vision.pipeline import ParcelVisionConfig, ParcelVisionPipeline
from parcel_vision.rgbd import CameraIntrinsics, depth_and_masks_to_labeled_cloud
from parcel_vision.stacked_scene import make_stacked_scene
from parcel_vision.stress import run_stress_suite


class ParcelVisionPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.points, cls.expected = make_synthetic_scene()
        cls.pipeline = ParcelVisionPipeline(
            ParcelVisionConfig(grid_size=5.0, plane_ransac_iterations=180)
        )
        cls.detections = cls.pipeline.process(cls.points)

    def test_detects_three_parcels(self):
        self.assertEqual(3, len(self.detections))

    def test_dimensions_and_grasp_positions(self):
        unmatched = list(self.detections)
        for expected in self.expected:
            detection = min(
                unmatched,
                key=lambda item: np.linalg.norm(
                    item.grasp_camera[:2] - np.asarray(expected["center"])
                ),
            )
            unmatched.remove(detection)
            self.assertLess(
                np.linalg.norm(detection.grasp_camera[:2] - np.asarray(expected["center"])),
                15.0,
            )
            self.assertAlmostEqual(expected["length"], detection.length, delta=15.0)
            self.assertAlmostEqual(expected["width"], detection.width, delta=15.0)
            self.assertAlmostEqual(1000.0 - expected["height"], detection.grasp_camera[2], delta=5.0)
            self.assertGreater(detection.score, 0.8)

    def test_camera_to_robot_transform(self):
        transform = np.eye(4)
        transform[:3, 3] = [100.0, -50.0, 20.0]
        transformed = self.pipeline.process(self.points, transform)
        by_size_original = sorted(self.detections, key=lambda item: item.length)
        by_size_transformed = sorted(transformed, key=lambda item: item.length)
        for original, robot in zip(by_size_original, by_size_transformed):
            np.testing.assert_allclose(
                robot.grasp_camera,
                original.grasp_camera + [100.0, -50.0, 20.0],
                atol=1e-6,
            )

    def test_protocol_response_is_json_serializable(self):
        response = build_protocol_response(self.detections, "tx-1", 123456, "arm1")
        encoded = json.dumps(response)
        self.assertEqual("package_location", response["tcp_cont"]["service_type"])
        self.assertEqual(3, len(response["svc_cont"]["message"]["data"]))
        self.assertIn('"device": "arm1"', encoded)

    def test_stress_suite_smoke(self):
        report = run_stress_suite(scene_count=3, seed=99)
        self.assertEqual(3, report["scene_count"])
        self.assertGreater(report["expected_parcels"], 0)
        self.assertGreater(report["matched_parcels"], 0)
        self.assertIn("position_error_mm", report)

    def test_morphology_radius_bridges_wider_depth_gap(self):
        points = np.array(
            [
                [x * 5.0, y * 5.0, 20.0]
                for start in (0, 6)
                for x in range(start, start + 3)
                for y in range(5)
            ]
        )
        small = ParcelVisionPipeline(
            ParcelVisionConfig(grid_size=5.0, min_area=1.0, morphology_radius=1)
        )
        large = ParcelVisionPipeline(
            ParcelVisionConfig(grid_size=5.0, min_area=1.0, morphology_radius=2)
        )

        small_labels, _, _ = small._segment_height_map(points)
        large_labels, _, _ = large._segment_height_map(points)

        self.assertEqual(2, small_labels.max())
        self.assertEqual(1, large_labels.max())

    def test_mixed_scene_contains_requested_parcel_types(self):
        scene = make_mixed_scene(np.random.default_rng(20260717), 10)

        self.assertEqual(10, len(scene.expected))
        self.assertEqual(
            {"cardboard_box", "soft_bag", "padded_mailer", "tube"},
            {parcel.kind for parcel in scene.expected},
        )
        self.assertTrue(np.isfinite(scene.points).all())

    def test_stacked_scene_keeps_all_ten_parcels_partly_visible(self):
        scene, _, visible_counts = make_stacked_scene(np.random.default_rng(20260718))

        self.assertEqual(10, len(scene.expected))
        self.assertEqual(set(range(1, 11)), set(visible_counts))
        self.assertTrue(all(count > 100 for count in visible_counts.values()))

        pipeline = ParcelVisionPipeline(
            ParcelVisionConfig(
                plane_distance_threshold=5.0,
                plane_ransac_iterations=180,
                segmentation_method="height_edges",
                height_edge_threshold=12.0,
                min_detection_score=0.75,
                max_local_roughness=15.0,
            )
        )
        frame = pipeline.fit_conveyor_plane(scene.points)
        detections = pipeline.process(scene.points)
        plan = build_grasp_plan(detections, frame)

        self.assertEqual(10, len(detections))
        self.assertEqual(2, plan["eligible_count"])
        self.assertIsNotNone(plan["recommended_object_id"])

    def test_depth_and_instance_masks_are_projected_to_labeled_points(self):
        depth = np.full((2, 3), 1000.0)
        masks = np.zeros((2, 2, 3), dtype=bool)
        masks[0, :, :2] = True
        masks[1, :, 2] = True

        points, labels = depth_and_masks_to_labeled_cloud(
            depth,
            masks,
            CameraIntrinsics(fx=1000.0, fy=1000.0, cx=1.0, cy=0.5),
        )

        np.testing.assert_allclose(points[0], [-1.0, -0.5, 1000.0])
        self.assertEqual([1, 1, 2, 1, 1, 2], labels.tolist())

    def test_labeled_instances_bypass_geometric_merging(self):
        labels = np.zeros(len(self.points), dtype=np.int32)
        for instance_id, expected in enumerate(self.expected, start=1):
            center = np.asarray(expected["center"])
            angle = np.radians(expected["yaw"])
            relative = self.points[:, :2] - center
            along = relative[:, 0] * np.cos(angle) + relative[:, 1] * np.sin(angle)
            across = -relative[:, 0] * np.sin(angle) + relative[:, 1] * np.cos(angle)
            selected = (
                (np.abs(along) <= expected["length"] / 2 + 2)
                & (np.abs(across) <= expected["width"] / 2 + 2)
                & (self.points[:, 2] < 990)
            )
            labels[selected] = instance_id

        detections = self.pipeline.process_labeled_instances(self.points, labels)

        self.assertEqual(3, len(detections))
        self.assertEqual(
            {"instance_0001", "instance_0002", "instance_0003"},
            {detection.object_id for detection in detections},
        )

    def test_instance_mask_does_not_fill_large_occlusion_hole(self):
        coordinates = []
        for x in range(0, 55, 5):
            for y in range(0, 55, 5):
                if not (15 <= x <= 35 and 15 <= y <= 35):
                    coordinates.append([x, y, 50.0])
        parcel = np.asarray(coordinates)

        component, origin = self.pipeline._instance_component_mask(parcel)
        center_cell = np.floor((np.array([25.0, 25.0]) - origin) / 5.0).astype(int)

        self.assertFalse(component[center_cell[1], center_cell[0]])

    def test_irregular_scene_contains_twelve_distinct_shapes(self):
        scene, truth_labels = make_irregular_scene(np.random.default_rng(20260719))

        self.assertEqual(12, len(scene.expected))
        self.assertEqual(12, len({parcel.kind for parcel in scene.expected}))
        self.assertEqual(set(range(1, 13)), set(np.unique(truth_labels[truth_labels > 0])))
        self.assertTrue(np.isfinite(scene.points).all())


if __name__ == "__main__":
    unittest.main()
