# The Docking Ascendancy (wip)
Predict protein-ligand complexes with Boltz-1 and optimize binders with BindCraft. Accelerate inference times and deploy molecular docking simulations in real-time

*Only the strongest ligands shall ascend.*

## Overview
The Docking Ascendancy aims to host trials for protein-ligand pairs. The platform begins with BindCraft for de novo binder assembly, followed by structure prediction comparisons across multiple models (AlphaFold3, Chai-1, and Boltz-1), providing interactive visualization and quantitative analysis of structural differences. This end-to-end workflow enables researchers to design novel binders and evaluate their structural predictions, with future capabilities planned for analyzing docking dynamics.

## ToDo

📊 Core Pipeline
- [x] Implement Boltz-1 prediction
- [x] Implement Chai-1 prediction
- [ ] Add AlphaFold3 prediction
- [ ] Integrate BindCraft assembly
- [ ] Create multi-model comparison dashboard
- [ ] Implement docking analysis

🔍 Analysis Tools
- [x] Basic structure visualization
- [x] Structure alignment & RMSD
- [ ] Add binding site analysis
- [ ] Implement additional metrics (TM-score, GDT)

🛠️ Technical
- [x] Set up Streamlit interface
- [x] Basic error handling
- [ ] Add comprehensive testing
- [ ] Improve performance & caching
- [ ] Add pipeline logging

📚 Documentation
- [x] Basic README
- [ ] Add installation guide
- [ ] Document best practices
