# The Docking Ascendancy (wip)
A Modal-powered platform for binder assembly and structure prediction, deployed as an accessible web interface. Design binders with BindCraft, predict structures with Boltz-1, Chai-1 and AlphaFold3, and analyze results through interactive visualization and alignment tools.

*Only the strongest ligands shall ascend.*

## Overview
The Docking Ascendancy aims to host trials for protein-ligand pairs. The platform begins with BindCraft for de novo binder assembly, followed by structure prediction comparisons across multiple models (AlphaFold3, Chai-1, and Boltz-1), providing interactive visualization and quantitative analysis of structural differences. This end-to-end workflow enables researchers to design novel binders and evaluate their structural predictions, with future capabilities planned for analyzing docking dynamics.

## ToDo

📊 Core Pipeline
- [x] Implement Boltz-1 prediction
- [x] Implement Chai-1 prediction
- [ ] Add AlphaFold3 prediction
- [ ] Integrate BindCraft assembly
- [ ] Create comparison dashboard
- [ ] Implement docking analysis

🔍 Analysis Tools
- [x] Basic structure visualization
- [x] Structure alignment & RMSD
- [ ] Add binding site analysis (Use LigUnity?! https://www.biorxiv.org/content/10.1101/2025.02.17.638554v1)
- [ ] Implement additional metrics (TM-score, GDT)

🛠️ Technical
- [x] Set up Streamlit interface
- [x] Basic error handling
- [ ] Add pipeline logging

📱 User Interface
- [x] Create Streamlit web application
- [x] Implement multi-page navigation
- [x] Create protein input page
- [x] Add structure prediction page
- [ ] Add output/dashboard/analysis page

📚 Documentation
- [x] Basic README
- [ ] Examples
- [ ] Add installation guide
- [ ] Document best practices

🔮 Future Desires
- [ ] Implement batch processing/prediction capabilities


