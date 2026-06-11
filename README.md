# Agentic Architecture Paper Recommender

Personal daily paper recommender for agentic computer architecture, architecture design space exploration, full-stack hardware/software co-design, CPU/GPU microarchitecture, simulators, and HPC cross-over work.

The target deployment model is serverless:

- GitHub Actions runs the daily pipeline.
- GitHub Pages hosts the static reading interface.
- Supabase stores feedback events.
- Email delivery is handled from GitHub Actions through SMTP.

The current repository starts with a self-contained MVP while upstream `daily-arXiv-ai-enhanced` integration is pending network availability.

## Initial Focus

- arXiv core categories: `cs.AR`, `cs.PF`, `cs.DC`, `cs.PL`
- arXiv expansion categories: `cs.AI`, `cs.LG`, filtered through a domain gate
- Recommendation sections:
  - Agentic Architecture / Auto-DSE
  - Full-stack HW/SW Co-design
  - CPU/GPU Microarchitecture and Simulators
  - HPC x Architecture / Compiler / Runtime
  - Exploratory but Maybe Relevant

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

