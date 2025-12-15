# AGENTIC AI SUMMIT 2025 – Hackathon & Technical Notes

🔗 **Official Summit Page**: [https://yp.ieeebangalore.org/ieee-yp-agentic-ai-summit-2025/](https://yp.ieeebangalore.org/ieee-yp-agentic-ai-summit-2025/)

This repository documents my **hackathon solution**, **hands-on experiments**, and **technical notes** from the **IEEE YP Agentic AI Summit 2025**. The focus is primarily on **Day 2**, which explored advanced concepts in **Agentic AI systems**, architectures, and real-world deployment considerations.

---

## 📌 Repository Purpose

This repo serves as:

* A record of my **hackathon work (Day 1 & Day 2)**
* Curated **technical notes** from expert sessions
* Conceptual explanations of **Agentic AI design patterns**
* Pointers to **notebooks and experiments** explored during the summit

While **Day 1** was largely introductory and hands-on, **Day 2** went deep into **non-deterministic agent behavior, meta-control, AI systems evolution, and frontier research**—which is the main emphasis of this repository.

---

## 🗂️ Repository Structure (High Level)

* `hackathon/` – My hackathon solution and implementation
* `notebooks/` – Experimental notebooks, demos, and explorations
* `notes/` – Conceptual and session-wise notes from the summit
* `README.md` – Summit summary, learnings, and references

---

## 🧠 Day 1 – Hands-on Foundations (Brief)

Day 1 focused on:

* Introduction to Agentic AI concepts
* Tool usage and basic agent workflows
* Hands-on experimentation and hackathon kickoff

These were primarily **practical starter sessions**, so detailed notes are limited compared to Day 2.

---

## 🚀 Day 2 – Advanced Agentic AI (Core Learnings)

### 1️⃣ Meta-Controller for Non-Deterministic Agents

A key takeaway from Day 2 was:

> **For non-deterministic agent systems, a Meta-Controller is essential.**

**Analogy**:

* Agents are like an **army**—powerful but chaotic without guidance
* The **Meta-Controller** acts as the **Captain**
* Individual agents follow tasks, but the captain defines:

  * Goals
  * Constraints
  * Execution order
  * Fallback and correction strategies

This is a foundational idea in **Agentic AI orchestration**, especially for:

* Multi-agent collaboration
* Tool-using LLMs
* Long-running workflows

---

### 2️⃣ On the Turing Test – A New Fear

> *“I am not afraid of AI passing the Turing Test.
> I am afraid of AI that deliberately fails it.”*

This highlights a shift in concern:

* Intelligence is no longer about imitation
* It is about **intentional behavior, deception, and alignment**

Agentic AI systems may **choose** how to present intelligence based on goals—raising serious questions around:

* Trust
* Safety
* Governance

---

### 3️⃣ Intelligence as High-Dimensional Vector Algebra

A philosophical yet mathematical insight:

> **Intelligence is vector algebra in high-dimensional space.**

* Concepts, images, language, and reasoning are embedded in latent spaces
* Learning is geometric alignment, not symbolic rules

This connects real-world problems with:

* Linear algebra
* Optimization
* Representation learning

---

## 📱 Samsung Session – Evolution of Consumer AI

Samsung presented the evolution of devices:

**Feature Phone → Smartphone → AI Phone**

Key discussion points:

* **ADLC (AI Development Life Cycle)**
* Privacy-first design
* On-device inference
* Built-in foundation models inside phones

This reflects a shift toward:

* Edge AI
* Personal AI agents
* Reduced cloud dependency

---

## 🔧 MediaTek Session – Compute & Monetization

Speaker: **Akshya Aggarwal**

Main insights:

* Compute demand is increasing exponentially
* Agentic AI is now **monetizable**, not just experimental
* Efficient resource utilization is critical

Agentic systems are becoming viable for business because:

* They reduce human-in-the-loop costs
* They enable autonomous decision-making
* Hardware-software co-design matters

---

## 🧬 Google DeepMind Session – Frontier Research

This was one of the most impactful sessions.

### 🔬 Co-Scientist Agent

* Inspired by **DNA double-helix replication**
* AI agents collaborate to:

  * Hypothesize
  * Experiment
  * Validate

This moves AI from *assistant* → *scientific collaborator*.

---

### 🎥 Veo 3

* Advanced video generation
* Improved temporal coherence
* High-fidelity creative outputs

---

### 🎶 Music AI Sandbox

* Demonstrated with **Sankar Mahadevan**
* Human-AI co-creation in music
* AI as a creative partner, not replacement

---

### 🧠 Matryoshka Models & Transformers

Key architectural ideas:

* **Matryoshka Models**: Nested representations for efficiency
* **Matryoshka Transformers**: Scalable inference
* **Tandem Transformers**:

  * Designed to handle **long-context inference**
  * Address **KV cache bottlenecks** in long-form generation

These techniques are critical for:

* Agent memory
* Long-horizon reasoning
* Cost-efficient deployment

---

## 📐 Agents vs Workflows – When Do You Really Need Agentic AI?

One important conceptual clarification from the summit (and supporting material) was the **distinction between Agents and fixed Workflows**.

### 🔹 Key Insight

> **If a problem can be represented along a single dimension with a predictable path, an Agentic workflow is unnecessary.**

In such cases, a **deterministic, fixed workflow** is:

* Easier to reason about
* Cheaper to run
* More reliable in production

### 🔹 One-Dimensional vs Multi-Dimensional Problems

* **One-dimensional graph** (linear decision path):

  * Inputs → Rules → Outputs
  * Minimal uncertainty
  * No exploration required
  * ✅ Prefer **traditional workflows / pipelines**

* **Multi-dimensional graph** (branching, uncertain paths):

  * Multiple decision points
  * Partial observability
  * Dynamic tool selection
  * ✅ Requires **Agentic systems**

Agentic AI becomes valuable only when the system must:

* Decide *what to do next*
* Recover from failures
* Adapt plans dynamically
* Operate under uncertainty

### 🔹 Practical Rule of Thumb

> **Do not use Agents where a workflow suffices.**

Overusing agents introduces:

* Unnecessary non-determinism
* Debugging complexity
* Higher compute cost

This framing helped ground Agentic AI as a **design choice**, not a default.

---

## 🧪 Notebooks & Experiments

This repository also includes:

* Exploratory notebooks
* Hackathon-related prototypes
* Agent orchestration experiments

These are intended as **learning artifacts**, not polished production systems.

---

## 🏁 Closing Thoughts

The summit clearly showed that:

* Agentic AI is moving from theory → production
* Control, alignment, and orchestration matter more than raw intelligence
* The future is **multi-agent, multimodal, and on-device**

This repository is my attempt to consolidate those learnings in a practical and reproducible way.

---

📌 *Feel free to explore, fork, or contribute.*
