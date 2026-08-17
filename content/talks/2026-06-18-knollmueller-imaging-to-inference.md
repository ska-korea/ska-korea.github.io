---
title: "From Imaging to Inference: Probabilistic Reconstruction of Physical Systems"
speaker: Jakob Knollmüller
affiliation: Max Planck Institute for Astrophysics
when: "6월 18일(목) 오후 4시"
where: 장영실홀 331-2
mode: offline
---

Many scientific measurements are indirect. Rather than observing the quantities of interest directly, instruments record incomplete and noisy data that must be interpreted through physical and statistical models. As a result, reconstruction is fundamentally an inference problem: the goal is not simply to obtain an image or signal estimate, but to determine what can be learned from the available information and what remains uncertain. In this talk, I will present a probabilistic approach to reconstruction in which signals, instrumental effects, and uncertainties are inferred jointly within a single framework. Instead of producing a single best-fit solution, the method aims to characterize the range of solutions that are consistent with both the data and prior knowledge.

I will illustrate these ideas with examples from astronomy, including dynamic radio interferometric imaging of black holes, all-sky gamma-ray imaging with Fermi, and adaptive signal modelling approaches that refine the underlying signal description as additional structure becomes apparent in the data. Despite their apparent differences, these applications share a common mathematical formulation that combines measurement models, prior information, and uncertainty estimates within a unified inference framework. Finally, I will give an overview of UBIK (Universal Bayesian Imaging Kit), an effort to build a modular framework for probabilistic field inference. The aim is to provide a common foundation on which instrument-specific measurement models can be combined with reusable signal models and inference techniques, allowing methods developed in one domain to be transferred more easily to others. In this way, UBIK seeks to move beyond instrument-specific reconstruction software toward a flexible, multi-instrument framework for scientific inference.
