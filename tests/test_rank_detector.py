import io
import json
import math
import random
import unittest
from contextlib import redirect_stdout

from branch_set import BranchStatus
from preference_free_rank import ReturnClass
from rank_detector import (
    MECHANISM_COLLAPSED,
    MECHANISM_ORIGIN,
    MECHANISM_SCALE_SUPPRESSED,
    MECHANISM_UNDERSAMPLED,
    SAMPLE_FLOOR,
    ActivatedDimension,
    DensitySweep,
    DetectionResult,
    Outcome,
    RankDetector,
    ScaleSample,
    anisotropic_noise_manifold,
    coarse_grain,
    crop,
    curved_manifold,
    density_sweep,
    eliminate_from_outcome,
    flat_manifold,
    local_dimension,
    main,
    manifold_frame,
    mechanism_branch_set,
    null_suite,
    order_test,
    participation_ratio,
    symmetric_eigen,
    thick_manifold,
)


def _cos(a, b):
    return abs(sum(x * y for x, y in zip(a, b)))


class LinearAlgebraTests(unittest.TestCase):
    def test_symmetric_eigen_recovers_known_spectrum(self):
        values, vectors = symmetric_eigen([[2, 1, 0], [1, 2, 0], [0, 0, 5]])
        self.assertEqual([round(v, 9) for v in values], [5.0, 3.0, 1.0])
        self.assertAlmostEqual(abs(vectors[0][2]), 1.0)
        self.assertAlmostEqual(_cos(vectors[1], (1, 1, 0)), math.sqrt(2))

    def test_symmetric_eigen_satisfies_eigen_equation(self):
        matrix = [[4.0, 1.0, 2.0], [1.0, 3.0, 0.0], [2.0, 0.0, 1.0]]
        values, vectors = symmetric_eigen(matrix)
        self.assertEqual(values, sorted(values, reverse=True))
        for value, vector in zip(values, vectors):
            self.assertAlmostEqual(math.sqrt(sum(x * x for x in vector)), 1.0)
            image = [sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3)]
            for i in range(3):
                self.assertAlmostEqual(image[i], value * vector[i], places=9)

    def test_symmetric_eigen_rejects_non_square(self):
        with self.assertRaises(ValueError):
            symmetric_eigen([[1, 2, 3], [2, 1, 0]])

    def test_participation_ratio(self):
        self.assertAlmostEqual(participation_ratio([1, 1, 1]), 3.0)
        self.assertAlmostEqual(participation_ratio([1, 0, 0]), 1.0)
        self.assertAlmostEqual(participation_ratio([-1e-12, 0.0]), 0.0)


class SweepTests(unittest.TestCase):
    def test_local_dimension_on_isotropic_ball(self):
        rng = random.Random(3)
        points = [(rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)) for _ in range(4000)]
        count, dim = local_dimension(points, (0.0, 0.0, 0.0), 1.0)
        self.assertGreater(count, 100)
        self.assertGreater(dim, 2.8)

    def test_local_dimension_below_floor_is_none(self):
        points = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
        count, dim = local_dimension(points, (0.0, 0.0), 0.1, min_neighbors=5)
        self.assertEqual(count, 1)
        self.assertIsNone(dim)

    def test_curve_holds_density_fixed_and_returns_every_scale(self):
        detector = RankDetector(n_scales=6)
        curve, per_center = detector.sweep(flat_manifold(800, 1, 2, seed=1))
        self.assertEqual(len(curve), 6)
        self.assertEqual(len(per_center), 32)
        radii = [sample.radius for sample in curve]
        self.assertEqual(radii, sorted(radii))
        for sample in curve:
            self.assertEqual(sample.centers_total, 32)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            RankDetector().detect([])
        with self.assertRaises(ValueError):
            RankDetector().detect([(0.0, 1.0), (1.0,)])
        with self.assertRaises(ValueError):
            RankDetector().detect([(0.0, float("nan"))])
        with self.assertRaises(ValueError):
            RankDetector(radii=[0.2, 0.1])
        with self.assertRaises(ValueError):
            RankDetector(min_scales=2)


class DetectionTests(unittest.TestCase):
    def test_flat_line_reads_flat_with_rank_one(self):
        result = RankDetector().detect(flat_manifold(2000, 1, 2, seed=1))
        self.assertIs(result.outcome, Outcome.FLAT)
        self.assertAlmostEqual(result.plateau_fine, 1.0, places=2)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.SCORED)
        self.assertAlmostEqual(criterion.value, 1.0, places=2)

    def test_flat_sheet_reads_flat_with_rank_two(self):
        result = RankDetector().detect(flat_manifold(2500, 2, 3, seed=1))
        self.assertIs(result.outcome, Outcome.FLAT)
        self.assertGreater(result.plateau_fine, 1.8)
        self.assertLess(result.plateau_fine, 2.05)

    def test_thick_ribbon_reads_activation_at_thickness_along_true_normal(self):
        thickness = 0.1
        points = thick_manifold(2500, 1, 3, thickness=thickness, seed=2)
        result = RankDetector().detect(points)
        self.assertIs(result.outcome, Outcome.ACTIVATION)
        self.assertGreater(result.k_step, thickness / 2)
        self.assertLess(result.k_step, thickness * 3)
        activated = result.activated
        self.assertIsNotNone(activated)
        self.assertGreater(_cos(activated.direction, manifold_frame(3, 2)[1]), 0.99)
        self.assertLess(activated.prior_variance, 0.15)
        self.assertGreater(activated.consistency, 0.99)
        self.assertLess(activated.null_space_isotropy, 0.1)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.VARIABLE_UNIDENT)
        payload = json.loads(criterion.note)
        self.assertAlmostEqual(payload["scale_of_appearance"], result.k_step)
        self.assertEqual(len(payload["activated_dimension"]["direction"]), 3)

    def test_more_samples_do_not_move_k_step(self):
        sparse = RankDetector().detect(thick_manifold(600, 1, 3, thickness=0.1, seed=2))
        dense = RankDetector().detect(thick_manifold(2400, 1, 3, thickness=0.1, seed=2))
        self.assertIs(sparse.outcome, Outcome.ACTIVATION)
        self.assertIs(dense.outcome, Outcome.ACTIVATION)
        self.assertLess(abs(math.log(sparse.k_step / dense.k_step)), math.log(1.5))

    def test_isotropic_off_manifold_noise_reads_noise_floor_not_activation(self):
        points = anisotropic_noise_manifold(2500, 1, 3, normal_sigma=0.01, seed=5)
        result = RankDetector().detect(points)
        self.assertIs(result.outcome, Outcome.NOISE_FLOOR)
        self.assertGreater(result.activated.null_space_isotropy, 0.5)
        self.assertIs(result.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_single_normal_direction_cannot_separate_noise_from_activation(self):
        # Documented limit: with one normal direction the geometry is identical.
        points = anisotropic_noise_manifold(2500, 1, 2, normal_sigma=0.01, seed=5)
        self.assertIs(RankDetector().detect(points).outcome, Outcome.ACTIVATION)

    def test_curvature_never_reads_activation(self):
        for curvature in (0.5, 4.0):
            points = curved_manifold(2500, 1, 2, curvature=curvature, seed=3)
            self.assertIsNot(RankDetector().detect(points).outcome, Outcome.ACTIVATION)
        strongly = curved_manifold(2500, 2, 3, curvature=4.0, seed=3)
        result = RankDetector().detect(strongly)
        self.assertIn(result.outcome, (Outcome.FLAT, Outcome.AMBIGUOUS, Outcome.COARSE_RISE))

    def test_closed_loop_reads_coarse_rise_not_activation(self):
        rng = random.Random(7)
        circle = [
            (math.cos(t), math.sin(t)) for t in (rng.uniform(0, 2 * math.pi) for _ in range(2500))
        ]
        detector = RankDetector(radii=[0.02 * 1.6 ** i for i in range(12)])
        result = detector.detect(circle)
        self.assertIs(result.outcome, Outcome.COARSE_RISE)
        self.assertGreater(result.plateau_coarse, result.plateau_fine)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.UNKNOWN_MEASURABLE)
        self.assertIn("graph", criterion.note)

    def test_nonuniform_density_reads_flat(self):
        points = flat_manifold(2500, 2, 3, seed=4, density_exponent=4.0)
        self.assertIs(RankDetector().detect(points).outcome, Outcome.FLAT)

    def test_too_few_points_is_blocked_on_sample_floor(self):
        result = RankDetector().detect(flat_manifold(12, 1, 2, seed=1))
        self.assertIs(result.outcome, Outcome.BLOCKED)
        self.assertEqual(result.blocker, SAMPLE_FLOOR)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.BLOCKED)
        self.assertEqual(criterion.blocker, SAMPLE_FLOOR)

    def test_result_round_trips_through_dict(self):
        result = RankDetector(n_scales=6).detect(flat_manifold(800, 1, 2, seed=1))
        encoded = json.dumps(result.to_dict(), sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["outcome"], "flat")
        self.assertEqual(len(decoded["curve"]), 6)


class CurveReaderTests(unittest.TestCase):
    """The reader is exercised on declared curves so each branch is pinned."""

    def read(self, dims, **overrides):
        radii = [0.01 * 1.5 ** i for i in range(len(dims))]
        curve = [ScaleSample(r, d, 32, 32) for r, d in zip(radii, dims)]
        return RankDetector(**overrides).read(curve)

    def test_flat(self):
        result = self.read([1.9, 1.95, 2.0, 2.0, 1.98, 2.0])
        self.assertIs(result.outcome, Outcome.FLAT)

    def test_step_fine_higher_is_activation_even_without_direction_data(self):
        result = self.read([3.0, 3.0, 2.9, 2.4, 2.05, 2.0, 2.0, 2.0])
        self.assertIs(result.outcome, Outcome.ACTIVATION)
        self.assertIsNone(result.activated)
        self.assertAlmostEqual(result.plateau_fine, 2.966, places=2)
        self.assertAlmostEqual(result.plateau_coarse, 2.0125, places=3)
        self.assertGreater(result.k_step, 0.01 * 1.5 ** 2)
        self.assertLess(result.k_step, 0.01 * 1.5 ** 4)
        self.assertIs(result.to_criterion_result().return_class, ReturnClass.VARIABLE_UNIDENT)

    def test_step_coarse_higher_is_coarse_rise(self):
        result = self.read([1.0, 1.0, 1.0, 1.2, 1.9, 2.0, 2.0, 2.0])
        self.assertIs(result.outcome, Outcome.COARSE_RISE)

    def test_monotone_drift_is_ambiguous(self):
        result = self.read([1.0, 1.1, 1.25, 1.4, 1.55, 1.7, 1.85, 2.0])
        self.assertIs(result.outcome, Outcome.AMBIGUOUS)
        self.assertIs(result.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_noisy_curve_without_plateau_is_blocked(self):
        result = self.read([1.0, 2.0, 1.2, 1.9, 1.1, 2.0, 1.3, 1.8])
        self.assertIs(result.outcome, Outcome.BLOCKED)
        self.assertEqual(result.blocker, SAMPLE_FLOOR)

    def test_fewer_than_min_scales_is_blocked(self):
        result = self.read([1.0, None, None, 1.0, 2.0])
        self.assertIs(result.outcome, Outcome.BLOCKED)


class NullConstructionTests(unittest.TestCase):
    def test_null_suite_reports_zero_false_positives_and_detects_control(self):
        report = null_suite(n_points=2000, seed=0)
        self.assertEqual(report.false_positive_rate, 0.0)
        self.assertEqual(set(report.per_family), {"anisotropic_noise", "curvature", "nonuniform_density"})
        self.assertTrue(report.positive_control_detected)
        for case in report.cases:
            self.assertEqual(case.true_rank, 1)
            self.assertIsNot(case.outcome, Outcome.ACTIVATION)
        text = report.format()
        self.assertIn("false-positive rate 0.00", text)
        self.assertIn("positive_control", text)
        json.dumps(report.to_dict())

    def test_null_suite_without_positive_control(self):
        report = null_suite(n_points=600, seed=1, positive_thickness=None)
        self.assertIsNone(report.positive_control_detected)
        self.assertEqual(len(report.cases), 7)


class DensityTests(unittest.TestCase):
    def test_flat_sheet_is_density_invariant(self):
        result = density_sweep(flat_manifold(2500, 2, 3, seed=1), 0.15)
        self.assertIs(result.rises, False)
        self.assertEqual([fraction for fraction, _ in result.samples], [0.25, 0.5, 1.0])

    def test_sparse_record_is_blocked(self):
        result = density_sweep(flat_manifold(300, 2, 3, seed=1), 0.05, min_neighbors=12)
        self.assertIsNone(result.rises)
        self.assertIn(SAMPLE_FLOOR, result.rule)


class OrderTests(unittest.TestCase):
    def test_crop_and_coarse_grain(self):
        points = [(float(i), 0.0) for i in range(10)]
        self.assertEqual(crop(points, (0.0, 0.0), 2.5), [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])
        grained = coarse_grain(points, 100.0)
        self.assertEqual(len(grained), 1)
        self.assertAlmostEqual(grained[0][0], 4.5)
        self.assertEqual(len(coarse_grain(points, 0.5)), 10)

    def test_zoom_in_and_zoom_out_commute_on_the_reading(self):
        result = order_test(flat_manifold(2500, 2, 3, seed=1), 0.3, 0.03)
        self.assertIsNotNone(result.commutator)
        self.assertLess(result.commutator, 0.1)
        self.assertTrue(result.commutes)
        self.assertGreater(result.record_discrepancy, 0.0)
        self.assertLess(result.record_discrepancy, 1.0)
        self.assertIn("commutes", result.rule)
        json.dumps(result.to_dict())

    def test_coarse_grain_above_read_scale_loses_the_reading(self):
        result = order_test(flat_manifold(1200, 2, 3, seed=1), 0.3, 0.25)
        self.assertIsNone(result.commutator)
        self.assertIsNone(result.commutes)
        self.assertIn(SAMPLE_FLOOR, result.rule)


class BranchSeamTests(unittest.TestCase):
    def test_mechanisms_are_one_branch_set_with_shared_origin(self):
        branch_set = mechanism_branch_set()
        ids = [branch.id for branch in branch_set.branches]
        self.assertEqual(ids, [MECHANISM_UNDERSAMPLED, MECHANISM_SCALE_SUPPRESSED, MECHANISM_COLLAPSED])
        self.assertEqual({branch.origin_pattern for branch in branch_set.branches}, {MECHANISM_ORIGIN})
        self.assertEqual({branch.discriminator for branch in branch_set.branches}.__len__(), 1)
        self.assertEqual({branch.cost for branch in branch_set.branches}, {1.0})
        self.assertEqual(branch_set.gap_list(), [])
        restored = type(branch_set).load(branch_set.serialize())
        self.assertEqual(restored, branch_set)

    def _activation(self):
        return DetectionResult(
            Outcome.ACTIVATION,
            rule="step",
            curve=[ScaleSample(0.01, 2.0, 32, 32), ScaleSample(0.1, 1.0, 32, 32)],
            k_step=0.03,
            plateau_fine=2.0,
            plateau_coarse=1.0,
            activated=ActivatedDimension(0.03, (0.0, 0.0, 1.0), 0.0, 1.0, 0.0, 32),
        )

    def _flat(self):
        return DetectionResult(
            Outcome.FLAT,
            rule="flat",
            curve=[ScaleSample(0.01, 1.0, 32, 32), ScaleSample(0.1, 1.0, 32, 32)],
            plateau_fine=1.0,
            plateau_coarse=1.0,
        )

    def test_activation_with_invariant_density_leaves_scale_suppressed(self):
        branch_set = mechanism_branch_set()
        density = DensitySweep(0.05, [(0.5, 2.0), (1.0, 2.0)], False, "invariant")
        eliminate_from_outcome(branch_set, self._activation(), density)
        self.assertIs(branch_set.get(MECHANISM_UNDERSAMPLED).status, BranchStatus.ELIMINATED)
        self.assertIs(branch_set.get(MECHANISM_COLLAPSED).status, BranchStatus.ELIMINATED)
        self.assertIs(branch_set.get(MECHANISM_SCALE_SUPPRESSED).status, BranchStatus.SURVIVED)
        self.assertEqual(len(branch_set.eliminated_set()), 2)

    def test_flat_with_rising_density_leaves_undersampled(self):
        branch_set = mechanism_branch_set()
        density = DensitySweep(0.05, [(0.5, 1.0), (1.0, 1.8)], True, "rises")
        eliminate_from_outcome(branch_set, self._flat(), density)
        self.assertIs(branch_set.get(MECHANISM_UNDERSAMPLED).status, BranchStatus.SURVIVED)
        self.assertIs(branch_set.get(MECHANISM_SCALE_SUPPRESSED).status, BranchStatus.ELIMINATED)
        self.assertIs(branch_set.get(MECHANISM_COLLAPSED).status, BranchStatus.ELIMINATED)

    def test_flat_without_density_keeps_two_open(self):
        branch_set = mechanism_branch_set()
        eliminate_from_outcome(branch_set, self._flat())
        self.assertEqual(
            [branch.id for branch in branch_set.test_queue()],
            [MECHANISM_COLLAPSED, MECHANISM_UNDERSAMPLED],
        )

    def test_ambiguous_and_blocked_eliminate_nothing(self):
        for outcome in (Outcome.AMBIGUOUS, Outcome.BLOCKED, Outcome.COARSE_RISE, Outcome.NOISE_FLOOR):
            branch_set = mechanism_branch_set()
            detection = DetectionResult(outcome, rule="x", curve=[], blocker=SAMPLE_FLOOR)
            eliminate_from_outcome(branch_set, detection)
            self.assertEqual(len(branch_set.test_queue()), 3)


class CliTests(unittest.TestCase):
    def test_null_command_prints_report(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["null", "--n-points", "500", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn("false_positive_rate", payload)

    def test_detect_command_reads_json_points(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "points.json"
            path.write_text(json.dumps(flat_manifold(800, 1, 2, seed=1)), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["detect", str(path)])
            self.assertEqual(code, 0)
            self.assertIn("flat", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
