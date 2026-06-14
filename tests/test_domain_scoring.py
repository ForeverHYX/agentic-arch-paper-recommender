import unittest

from paper_recommender.domain import Paper, classify_paper, rank_papers


class DomainScoringTests(unittest.TestCase):
    def test_expansion_ai_paper_needs_architecture_gate(self):
        paper = Paper(
            paper_id="noise-1",
            title="A RAG Agent Benchmark for Web Task Automation",
            abstract=(
                "We evaluate multi-agent software frameworks for browser tasks, "
                "retrieval augmented generation, and tool use."
            ),
            authors=["A. Researcher"],
            categories=["cs.AI"],
        )

        result = classify_paper(paper)

        self.assertFalse(result.accepted)
        self.assertIn("generic-ai-agent-noise", result.negative_matches)

    def test_agentic_microarchitecture_paper_is_high_confidence_match(self):
        paper = Paper(
            paper_id="archagent-1",
            title="Agentic AI-Driven Microarchitecture Design Space Exploration",
            abstract=(
                "An LLM-driven hardware design agent explores cache replacement "
                "policy and data prefetcher candidates through cycle-accurate "
                "simulation with gem5 for computer architecture discovery."
            ),
            authors=["B. Architect"],
            categories=["cs.AI", "cs.AR"],
        )

        result = classify_paper(paper)

        self.assertTrue(result.accepted)
        self.assertGreaterEqual(result.score, 10)
        self.assertIn("agentic_architecture", result.sections)
        self.assertIn("microarchitecture_simulators", result.sections)

    def test_core_architecture_category_accepts_gpu_simulator_hpc_cross_over(self):
        paper = Paper(
            paper_id="gpu-hpc-1",
            title="GPU Microarchitecture Simulation for Exascale HPC Workloads",
            abstract=(
                "We extend Accel-Sim and GPGPU-Sim to study SIMT warp scheduling, "
                "memory bandwidth, interconnect pressure, and performance portability "
                "for high performance computing applications."
            ),
            authors=["C. Systems"],
            categories=["cs.AR", "cs.DC"],
        )

        result = classify_paper(paper)

        self.assertTrue(result.accepted)
        self.assertIn("microarchitecture_simulators", result.sections)
        self.assertIn("hpc_cross_over", result.sections)

    def test_hardware_aware_nas_is_recovered_as_codesign_not_generic_noise(self):
        paper = Paper(
            paper_id="codesign-1",
            title="Hardware-Aware Neural Architecture Search for RISC-V Accelerators",
            abstract=(
                "The method performs compiler architecture co-design for a RISC-V "
                "custom extension and domain-specific accelerator, using MLIR to "
                "jointly optimize workload mapping and hardware-aware schedules."
            ),
            authors=["D. Codesign"],
            categories=["cs.LG"],
        )

        result = classify_paper(paper)

        self.assertTrue(result.accepted)
        self.assertIn("full_stack_codesign", result.sections)
        self.assertNotIn("generic-nas-noise", result.negative_matches)

    def test_rank_papers_prioritizes_agentic_architecture_over_generic_hpc(self):
        agentic = Paper(
            paper_id="agentic",
            title="LLM-Driven Architecture Idea Factory for Branch Predictor Design",
            abstract=(
                "Agentic AI performs microarchitecture optimization and simulator-guided "
                "design space exploration for branch predictor and cache hierarchy designs."
            ),
            authors=["E. Agent"],
            categories=["cs.AI", "cs.AR"],
        )
        hpc = Paper(
            paper_id="hpc",
            title="Communication-Avoiding Sparse Linear Algebra on Exascale Systems",
            abstract=(
                "We optimize MPI and OpenMP sparse linear algebra kernels for NUMA systems "
                "and memory bandwidth."
            ),
            authors=["F. HPC"],
            categories=["cs.DC"],
        )

        ranked = rank_papers([hpc, agentic])

        self.assertEqual([item.paper.paper_id for item in ranked], ["agentic"])

    def test_generic_hpc_without_architecture_signal_is_not_accepted(self):
        paper = Paper(
            paper_id="generic-hpc",
            title="Communication-Avoiding Sparse Linear Algebra on Exascale Systems",
            abstract=(
                "We optimize MPI and OpenMP sparse linear algebra kernels for large "
                "HPC clusters using NUMA placement and memory bandwidth tuning."
            ),
            authors=["H. Compute"],
            categories=["cs.DC", "cs.PF"],
        )

        result = classify_paper(paper)

        self.assertFalse(result.accepted)
        self.assertIn("generic-hpc-noise", result.negative_matches)

    def test_hpc_with_microarchitecture_signal_is_still_accepted(self):
        paper = Paper(
            paper_id="architecture-hpc",
            title="GPU Microarchitecture Simulation for Exascale HPC Workloads",
            abstract=(
                "We use Accel-Sim to study SIMT warp scheduling, cache hierarchy, "
                "interconnect pressure, and GPU microarchitecture bottlenecks."
            ),
            authors=["A. Systems"],
            categories=["cs.AR", "cs.DC"],
        )

        result = classify_paper(paper)

        self.assertTrue(result.accepted)
        self.assertIn("microarchitecture_simulators", result.sections)
        self.assertIn("hpc_cross_over", result.sections)
        self.assertNotIn("generic-hpc-noise", result.negative_matches)

    def test_short_keywords_do_not_match_inside_longer_words(self):
        paper = Paper(
            paper_id="codesign",
            title="Compiler Architecture Co-design for RISC-V Custom Accelerators",
            abstract=(
                "The method performs full-stack co-design across MLIR, runtime scheduling, "
                "workload mapping, and a RISC-V custom extension."
            ),
            authors=["G. Compiler"],
            categories=["cs.PL", "cs.AR"],
        )

        result = classify_paper(paper)

        self.assertIn("full_stack_codesign", result.sections)
        self.assertNotIn("hpc_cross_over", result.sections)
        self.assertFalse(any(match == "hpc_cross_over:mpi" for match in result.positive_matches))


if __name__ == "__main__":
    unittest.main()
