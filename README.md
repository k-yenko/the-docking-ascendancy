# The Docking Ascendancy (wip)
Predict protein-ligand complexes with Boltz-1 and optimize binders with BindCraft. Accelerate inference times and deploy molecular docking simulations in real-time

*Only the strongest ligands shall ascend.*

## Overview
Built on top of Boltz-1, the Docking Ascendancy aims to host trials for protein-ligand pairs. This project aims to run complex predictions in parallel, optimize binders, optimize for real-time performance, and deploy a scalable API. 

## Roadmap
1. Setup and baseline testing
2. Batch processing (Boltz-1 runs in parallel to generate docking poses, one target protein multiple ligands)
3. Docking results filtered for high-confidence binders (just use confidence_scores)
4. Top-scoring binders are passed to BindCraft for optimization
5. Optimized binder sequences are stored and re-evaluated with Boltz-1
6. ONNX to make docking predictions faster
7. FastAPI for real-time binder design
8. Validation and testing
9. Documentation
