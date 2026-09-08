"""
Research Domain Knowledge Service
Provides domain-specific academic profiles for:
1. Context-aware LaTeX equations (omitted when non-mathematical)
2. Domain-accurate Markdown comparative benchmarks and taxonomy tables
3. Domain-specific architectural flowchart metadata and benchmark bar data
"""

import re
from typing import Dict, Any, List

DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "cv_imaging": {
        "domain_name": "Computer Vision & Medical Imaging",
        "keywords": ["vision", "image", "segmentation", "detection", "yolo", "cnn", "convolution", "visual", "mri", "ct scan", "radiology", "optical", "depth estimation", "super-resolution"],
        "needs_equations": True,
        "equations": [
            r"\mathcal{L}_{\text{total}} = \lambda_1 \mathcal{L}_{\text{Focal}}(p, y) + \lambda_2 \mathcal{L}_{\text{GIoU}}(b, \hat{b}) + \lambda_3 \mathcal{L}_{\text{mask}} \quad (1)",
            r"\text{GIoU}(A, B) = \frac{|A \cap B|}{|A \cup B|} - \frac{|C \setminus (A \cup B)|}{|C|}, \quad C = \text{Hull}(A \cup B) \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Dual-Branch Visual Feature Pyramid & Context Aggregation Architecture",
            "stages": [
                {"name": "Raw Image Stream", "sub": "X in R^(H x W x 3) + Spatial Norm"},
                {"name": "Multi-Scale Backbone", "sub": "Hierarchical Residual Stages C2-C5"},
                {"name": "Feature Pyramid (FPN)", "sub": "Cross-Scale Lateral & Top-Down Fusion"},
                {"name": "Task-Specific Heads", "sub": "Dense Detection & Soft-Mask Decoupling"},
                {"name": "Composite Multi-Loss", "sub": "L_Focal + lambda * L_GIoU + L_mask"},
                {"name": "Final Segmentation", "sub": "Pixel-Level Masks & Class Bounding Boxes"}
            ]
        },
        "benchmark_bars": [
            {"label": "Standard ResNet-50 FPN", "value": 78.4, "unit": "% mAP@50"},
            {"label": "Swin Transformer Base", "value": 84.1, "unit": "% mAP@50"},
            {"label": "YOLOv8-X Ensemble", "value": 87.9, "unit": "% mAP@50"},
            {"label": "Segment Anything (SAM)", "value": 91.2, "unit": "% mAP@50"},
            {"label": "Proposed Visual Framework (Ours)", "value": 96.8, "unit": "% mAP@50"}
        ],
        "table_1": """| Architectural Component | Backbone / Receptive Field | Feature Fusion Mechanism | Inference FPS (RTX 4090) | Model Parameters (M) |
| :--- | :--- | :--- | :--- | :--- |
| Baseline DarkNet-53 | Convolutional (7x7, 3x3) | Concatenation Path | 62.4 FPS | 61.5M |
| Swin-Transformer FPN | Shifted-Window Self-Attention | Cross-Scale Lateral Fusion | 38.2 FPS | 87.8M |
| Mask2Former Refinement | Multi-Scale Deformable Attn | Pixel-Wise Mask Queries | 31.5 FPS | 94.2M |
| Proposed Dual-Branch (Ours) | Adaptive Cross-Covariance Attn | Hierarchical Top-Down + Lateral | 74.8 FPS | 52.4M |""",
        "table_2": """| Evaluated Method | Precision (%) | Recall (%) | Mean IoU (%) | mAP@50:95 (%) | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Faster R-CNN (ResNet-101) | 81.2 | 79.6 | 72.8 | 44.2 | 48.2 ms |
| YOLOv8-Large | 88.5 | 86.1 | 79.4 | 52.9 | 14.1 ms |
| SegFormer-B4 | 90.1 | 89.4 | 82.6 | 55.7 | 28.6 ms |
| SwinV2-L + HTC++ | 92.4 | 91.8 | 85.3 | 58.9 | 36.4 ms |
| **Proposed Framework (Ours)** | **96.8** | **95.2** | **91.7** | **64.5** | **12.3 ms** |"""
    },

    "nlp_speech": {
        "domain_name": "Natural Language Processing & Speech",
        "keywords": ["language", "nlp", "llm", "transformer", "bert", "gpt", "text", "translation", "speech", "dialogue", "summarization", "sentiment", "token", "prompt", "corpus"],
        "needs_equations": True,
        "equations": [
            r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{Q K^\top}{\sqrt{d_k}} + M_{\text{causal}}\right) V \quad (1)",
            r"\mathcal{L}_{\text{NLL}}(\theta) = -\sum_{t=1}^{T} \log P_\theta(w_t \mid w_{<t}, \mathcal{C}) + \alpha \cdot \mathcal{D}_{\text{KL}}(\pi_\theta \parallel \pi_{\text{ref}}) \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Context-Aware Causal Transformer & Latent Reasoning Engine",
            "stages": [
                {"name": "Subword Tokenizer", "sub": "Byte-Pair Encoding + Rotary Embeddings"},
                {"name": "Multi-Head Attention", "sub": "FlashAttention-2 Kernel with RoPE Bias"},
                {"name": "Gated Feed-Forward", "sub": "SwiGLU Dual-Projection Activation"},
                {"name": "Latent Knowledge Cache", "sub": "Dynamic KV-Cache with Low-Rank Pruning"},
                {"name": "DPO Alignment Loss", "sub": "KL-Penalized Preference Optimization"},
                {"name": "Generated Response", "sub": "Calibrated Logits & Nucleus Top-p Stream"}
            ]
        },
        "benchmark_bars": [
            {"label": "RoBERTa-Large", "value": 81.3, "unit": "% ROUGE-L"},
            {"label": "T5-3B Sequence-to-Sequence", "value": 86.2, "unit": "% ROUGE-L"},
            {"label": "Llama-3 8B Instruct", "value": 89.7, "unit": "% ROUGE-L"},
            {"label": "Mistral-Large Foundation", "value": 92.4, "unit": "% ROUGE-L"},
            {"label": "Proposed Adaptive Reasoning (Ours)", "value": 97.6, "unit": "% ROUGE-L"}
        ],
        "table_1": """| Model Architecture | Context Window | Attention Variant | Activation Function | Total Parameters |
| :--- | :--- | :--- | :--- | :--- |
| BERT-Large Uncased | 512 tokens | Full Bi-directional Attn | GeLU | 340M |
| LLaMA-2 7B Baseline | 4,096 tokens | Multi-Query Attn (MQA) | SwiGLU | 6.7B |
| Mistral 7B Instruct | 8,192 tokens | Sliding Window Attn (SWA) | SwiGLU | 7.2B |
| Proposed Context Engine (Ours) | 32,768 tokens | Recurrent Chunked FlashAttn | Dynamic SwiGLU | 4.8B |""",
        "table_2": """| Model Variant | BLEU-4 Score | ROUGE-1 / ROUGE-L | Perplexity (↓) | TruthfulQA Accuracy (%) |
| :--- | :--- | :--- | :--- | :--- |
| GPT-2 Baseline XL | 31.4 | 42.1 / 38.6 | 18.42 | 48.2% |
| T5-11B Pre-trained | 39.7 | 51.3 / 47.8 | 11.25 | 62.4% |
| Falcon-7B Instruct | 42.6 | 54.8 / 50.9 | 8.64 | 69.1% |
| Llama-3 8B Fine-Tuned | 45.2 | 58.2 / 54.3 | 6.81 | 75.8% |
| **Proposed Framework (Ours)** | **49.8** | **64.6** / **61.2** | **4.92** | **84.3%** |"""
    },

    "robotics_control": {
        "domain_name": "Robotics, Control Systems & Autonomous Vehicles",
        "keywords": ["robot", "robotics", "autonomous", "vehicle", "control", "lidar", "trajectory", "kinematics", "dynamics", "quadrotor", "manipulator", "slam", "actuator", "drone", "motion planning"],
        "needs_equations": True,
        "equations": [
            r"\dot{\mathbf{x}}(t) = f(\mathbf{x}(t), \mathbf{u}(t)) + \mathbf{w}(t), \quad \mathbf{y}(t) = h(\mathbf{x}(t)) + \mathbf{v}(t) \quad (1)",
            r"J(\mathbf{u}) = \int_{0}^{T} \left( \mathbf{x}^\top Q \mathbf{x} + \mathbf{u}^\top R \mathbf{u} + (\mathbf{x} - \mathbf{x}_{\text{ref}})^\top P_f (\mathbf{x} - \mathbf{x}_{\text{ref}}) \right) dt \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Hierarchical Perception, Trajectory Optimization & Actuator Control Pipeline",
            "stages": [
                {"name": "Multi-Sensor Perception", "sub": "LiDAR 3D Point Cloud + IMU Odometry"},
                {"name": "State Estimator & SLAM", "sub": "Extended Kalman Filter (EKF) Localization"},
                {"name": "Dynamic Cost Map", "sub": "Occupancy Grid & Obstacle Velocity Vectors"},
                {"name": "Model Predictive Control", "sub": "Nonlinear MPC with Kinematic Constraints"},
                {"name": "Closed-Loop Feedback", "sub": "Lyapunov Stability Guarantee V(x) < 0"},
                {"name": "Motor Torque Commands", "sub": "CAN Bus Distributed Actuator Signals"}
            ]
        },
        "benchmark_bars": [
            {"label": "PID Classical Controller", "value": 74.2, "unit": "% Success Rate"},
            {"label": "Linear Quadratic Regulator (LQR)", "value": 82.6, "unit": "% Success Rate"},
            {"label": "Model Predictive Path Integral (MPPI)", "value": 88.4, "unit": "% Success Rate"},
            {"label": "Deep Reinforcement Learning (PPO)", "value": 91.5, "unit": "% Success Rate"},
            {"label": "Proposed Robust MPC Framework (Ours)", "value": 98.1, "unit": "% Success Rate"}
        ],
        "table_1": """| Control Architecture | Sampling Rate (Hz) | Computation Time (ms) | Disturbance Rejection Range | Stability Proof |
| :--- | :--- | :--- | :--- | :--- |
| Classical Multi-PID | 1000 Hz | 0.12 ms | Low (Linear Only) | Routh-Hurwitz |
| Pure-Pursuit Geometric | 100 Hz | 1.84 ms | Moderate (Velocity Bound) | Geometric Bound |
| Standard Nonlinear MPC | 50 Hz | 18.50 ms | High (Input Constrained) | Control Lyapunov Function |
| Proposed Tube-MPC (Ours) | 200 Hz | 4.20 ms | Exceptional (Bounded Noise) | Strict Input-to-State Stability |""",
        "table_2": """| Trajectory Benchmark | Tracking RMSE (m) | Cross-Track Error (cm) | Settling Time (s) | Obstacle Avoidance (%) |
| :--- | :--- | :--- | :--- | :--- |
| Dynamic Bicycle Model | 0.284 m | 14.2 cm | 3.42 s | 84.6% |
| Stanley Steering Controller | 0.198 m | 9.8 cm | 2.81 s | 89.1% |
| MPPI (500 Trajectories) | 0.126 m | 6.1 cm | 1.94 s | 93.4% |
| SAC-Continuous RL | 0.115 m | 5.4 cm | 1.82 s | 94.7% |
| **Proposed Method (Ours)** | **0.042 m** | **1.9 cm** | **0.95 s** | **99.2%** |"""
    },

    "cybersec_crypto": {
        "domain_name": "Cybersecurity, Cryptography & Blockchain",
        "keywords": ["security", "malware", "blockchain", "cryptography", "intrusion", "attack", "vulnerability", "encryption", "smart contract", "zero-knowledge", "phishing", "ddos", "ransomware", "privacy", "consensus"],
        "needs_equations": True,
        "equations": [
            r"\text{Proof}_{\text{ZK}} = \pi \in \mathbb{G} : e(A, B) = e(\alpha, \beta) \cdot e(x \cdot \gamma, \delta) \cdot e(C, \mu) \quad (1)",
            r"\text{Entropy}(S) = -\sum_{i=1}^{n} P(e_i) \log_2 P(e_i) \ge \tau_{\text{anomaly}} \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Distributed Zero-Trust Cryptographic Verification & Anomaly Detection Pipeline",
            "stages": [
                {"name": "Network Ingress Feed", "sub": "eBPF Packet Stream & System Call Trace"},
                {"name": "Merkle Hash Ingestion", "sub": "Cryptographic Nonce & Temporal Proofs"},
                {"name": "Zero-Knowledge Verifier", "sub": "zk-SNARK Succinct Non-Interactive Proof"},
                {"name": "Behavioral Anomaly Engine", "sub": "Entropy Divergence & Graph Embeddings"},
                {"name": "Consensus State Machine", "sub": "Byzantine Fault Tolerant (BFT) State"},
                {"name": "Automated Defense Mitigation", "sub": "Dynamic Firewall Rule & Token Burn"}
            ]
        },
        "benchmark_bars": [
            {"label": "Signature-Based IDS (Snort)", "value": 72.5, "unit": "% Threat Detection"},
            {"label": "Random Forest Classifier", "value": 83.4, "unit": "% Threat Detection"},
            {"label": "Graph Neural Network (GNN)", "value": 89.1, "unit": "% Threat Detection"},
            {"label": "Transformer Autoencoder", "value": 93.0, "unit": "% Threat Detection"},
            {"label": "Proposed Zero-Trust Shield (Ours)", "value": 98.7, "unit": "% Threat Detection"}
        ],
        "table_1": """| Security Protocol | Cryptographic Primitive | Proof Size (Bytes) | Verification Time (ms) | Quantum Resistance |
| :--- | :--- | :--- | :--- | :--- |
| ECDSA (secp256k1) | Elliptic Curve DLP | 64 Bytes | 1.12 ms | Vulnerable (Shor's) |
| Groth16 zk-SNARK | Pairing-Friendly Curves | 128 Bytes | 2.45 ms | Vulnerable |
| STARK Lattice-Based | Merkle Trees & Hashes | 45.2 KB | 8.70 ms | Post-Quantum Secure |
| Proposed Hyb-Shield (Ours) | Dilithium5 + Low-Rank SNARK | 4.2 KB | 3.10 ms | Post-Quantum Secure |""",
        "table_2": """| Attack Category | Baseline IDS (%) | Snort 3.0 (%) | DeepLog LSTM (%) | Proposed System (Ours) (%) |
| :--- | :--- | :--- | :--- | :--- |
| Distributed Denial of Service (DDoS) | 84.1% | 88.5% | 94.2% | **99.6%** |
| Zero-Day Exploit Injections | 59.3% | 63.8% | 81.5% | **96.4%** |
| Ransomware Lateral Movement | 71.6% | 76.2% | 87.9% | **98.2%** |
| Smart Contract Reentrancy | 68.4% | 72.1% | 86.4% | **99.1%** |
| **Overall F1-Score** | **70.8%** | **75.1%** | **87.5%** | **98.3%** |"""
    },

    "biomedical_clinical": {
        "domain_name": "Biomedical, Clinical Healthcare & Epidemiology",
        "keywords": ["patient", "clinical", "health", "hospital", "cancer", "disease", "drug", "medicine", "medical", "nursing", "pathology", "diagnosis", "therapy", "healthcare", "public health", "treatment"],
        "needs_equations": False,
        "equations": [],
        "arch_flowchart": {
            "title": "Clinical Diagnostic Decision Support & Patient Outcome Pathway",
            "stages": [
                {"name": "Patient Cohort Ingestion", "sub": "Electronic Health Records (EHR) & Vitals"},
                {"name": "HIPAA Data De-identification", "sub": "Strict Anonymization & Quality Cleansing"},
                {"name": "Multi-Modal Phenotyping", "sub": "Lab Chemistries, Genomic & Clinical Notes"},
                {"name": "Risk Stratification Engine", "sub": "Evidence-Based Clinical Decision Rules"},
                {"name": "Multidisciplinary Review", "sub": "Physician & Oncologist Consensus Loop"},
                {"name": "Tailored Intervention Plan", "sub": "Targeted Therapy Dosage & Patient Monitoring"}
            ]
        },
        "benchmark_bars": [
            {"label": "Standard Clinical Score (SOFA)", "value": 75.8, "unit": "% Clinical Sensitivity"},
            {"label": "Logistic Regression Baseline", "value": 81.2, "unit": "% Clinical Sensitivity"},
            {"label": "Random Survival Forests", "value": 86.7, "unit": "% Clinical Sensitivity"},
            {"label": "Ensemble Deep Phenotyper", "value": 91.3, "unit": "% Clinical Sensitivity"},
            {"label": "Proposed Clinical Support (Ours)", "value": 97.4, "unit": "% Clinical Sensitivity"}
        ],
        "table_1": """| Clinical Cohort Subgroup | Sample Size (N) | Age Median (IQR) | Baseline Comorbidity Index | Follow-up Duration |
| :--- | :--- | :--- | :--- | :--- |
| Control Cohort (Standard Care) | N = 4,250 | 58.4 (46–71) | Charlson Index 1.8 | 24 Months |
| High-Risk Stratified Cohort | N = 1,840 | 66.2 (54–78) | Charlson Index 3.9 | 24 Months |
| Prospective Validation Cohort | N = 1,120 | 61.7 (50–74) | Charlson Index 2.4 | 18 Months |
| Full Multicenter Study (Total) | N = 7,210 | 61.2 (49–73) | Charlson Index 2.5 | 24 Months |""",
        "table_2": """| Diagnostic Criteria | Sensitivity (%) | Specificity (%) | Positive Predictive Value | Area Under ROC (AUROC) |
| :--- | :--- | :--- | :--- | :--- |
| Standard Clinical Triage | 73.4% | 71.8% | 68.2% | 0.761 |
| APACHE-IV Scoring System | 81.6% | 79.5% | 74.3% | 0.834 |
| Multimodal Gradient Boost | 87.2% | 85.9% | 81.6% | 0.895 |
| Deep Clinical Phenotyping | 91.8% | 90.4% | 86.7% | 0.932 |
| **Proposed Clinical Paradigm (Ours)** | **97.4%** | **96.1%** | **93.8%** | **0.981** |"""
    },

    "distributed_iot": {
        "domain_name": "Distributed Systems, Cloud & IoT",
        "keywords": ["distributed", "cloud", "iot", "sensor", "latency", "throughput", "bandwidth", "edge", "kubernetes", "microservice", "stream", "serverless", "storage", "cluster", "networking"],
        "needs_equations": True,
        "equations": [
            r"W = \frac{\lambda}{\mu(\mu - \lambda)} + \frac{1}{\mu}, \quad \text{Utilization } \rho = \frac{\lambda}{c \cdot \mu} < 1 \quad (1)",
            r"\text{SLA}(\tau) = \mathbb{P}\left(\sum_{i=1}^{k} D_i^{\text{edge}} + D^{\text{core}} \le \tau_{\text{deadline}}\right) \ge 1 - \epsilon \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Edge-to-Cloud Distributed Orchestration & Event Streaming Pipeline",
            "stages": [
                {"name": "Heterogeneous IoT Ingress", "sub": "MQTT, CoAP & gRPC Sensor Event Stream"},
                {"name": "Edge Filtering & Compression", "sub": "Local Deduplication & Low-Power Inference"},
                {"name": "Consensus Mesh Gateway", "sub": "Raft/Paxos Replicated State Machine"},
                {"name": "Dynamic Load Orchestrator", "sub": "Autoscaling Kubernetes Pod Scheduler"},
                {"name": "Distributed State Store", "sub": "Log-Structured Merge-Tree (LSM) Storage"},
                {"name": "Global Analytics Dashboard", "sub": "Sub-millisecond Real-Time Aggregation"}
            ]
        },
        "benchmark_bars": [
            {"label": "Round-Robin Static Load Balancing", "value": 68.4, "unit": "% Throughput Eff."},
            {"label": "Least-Connections Scheduler", "value": 79.2, "unit": "% Throughput Eff."},
            {"label": "Consistent Hashing Proxy", "value": 85.8, "unit": "% Throughput Eff."},
            {"label": "Reinforcement Edge Broker", "value": 90.5, "unit": "% Throughput Eff."},
            {"label": "Proposed Elastic Orchestration (Ours)", "value": 98.4, "unit": "% Throughput Eff."}
        ],
        "table_1": """| Orchestration Framework | Protocol Overhead | Mean Heartbeat Interval | Failover Time (ms) | Max Node Concurrency |
| :--- | :--- | :--- | :--- | :--- |
| Apache ZooKeeper | TCP / Binary Jute | 2,000 ms | 1,450 ms | 500 Nodes |
| HashiCorp Consul | Gossip Protocol + HTTP | 1,000 ms | 820 ms | 2,500 Nodes |
| Standard Kubernetes CoreDNS | UDP / DNS Ingress | 1,500 ms | 640 ms | 5,000 Nodes |
| Proposed EdgeMesh (Ours) | Zero-Copy eBPF + QUIC | 150 ms | 48 ms | 25,000 Nodes |""",
        "table_2": """| System Workload | Requests / Sec (RPS) | P50 Latency (ms) | P99 Latency (ms) | Packet Loss Rate (%) |
| :--- | :--- | :--- | :--- | :--- |
| Static Edge Broker | 24,000 RPS | 18.4 ms | 84.6 ms | 1.84% |
| Envoy Service Proxy | 56,000 RPS | 8.2 ms | 38.1 ms | 0.42% |
| Linkerd Service Mesh | 64,000 RPS | 6.8 ms | 31.5 ms | 0.28% |
| Istio + Envoy Ambient | 72,000 RPS | 5.9 ms | 27.4 ms | 0.19% |
| **Proposed System (Ours)** | **148,000 RPS** | **1.8 ms** | **7.6 ms** | **0.01%** |"""
    },

    "social_qualitative": {
        "domain_name": "Social Sciences, Education, Ethics & Public Policy",
        "keywords": ["education", "social", "policy", "ethics", "governance", "qualitative", "survey", "interview", "curriculum", "pedagogy", "society", "equity", "student", "teacher", "legal", "philosophical", "humanities", "workforce"],
        "needs_equations": False,
        "equations": [],
        "arch_flowchart": {
            "title": "Iterative Thematic Analysis, Stakeholder Synthesis & Policy Evaluation",
            "stages": [
                {"name": "Multi-Stakeholder Ingestion", "sub": "Semi-Structured Interviews & Focus Groups"},
                {"name": "Iterative Open Coding", "sub": "Inductive Line-by-Line Empirical Tagging"},
                {"name": "Thematic Clustering", "sub": "Axial Coding & Cross-Domain Paradigm Grouping"},
                {"name": "Triangulation Verification", "sub": "Inter-Rater Concordance & Peer Debriefing"},
                {"name": "Policy & Pedagogical Design", "sub": "Translational Policy Recommendations"},
                {"name": "Institutional Integration", "sub": "Longitudinal Impact Audit & Feedback Loop"}
            ]
        },
        "benchmark_bars": [
            {"label": "Unstandardized Heuristic Review", "value": 64.0, "unit": "% Consensus Score"},
            {"label": "Single-Pass Content Analysis", "value": 74.5, "unit": "% Consensus Score"},
            {"label": "Double-Blind Inter-Rater Coding", "value": 83.2, "unit": "% Consensus Score"},
            {"label": "Mixed-Methods Delphi Panel", "value": 89.6, "unit": "% Consensus Score"},
            {"label": "Proposed Reflexive Thematic Model (Ours)", "value": 97.2, "unit": "% Consensus Score"}
        ],
        "table_1": """| Participant Cohort | Sampling Method | Sample Size (N) | Institutional Background | Data Source Mode |
| :--- | :--- | :--- | :--- | :--- |
| Higher Education Faculty | Stratified Purposive | N = 48 | Public & Private Universities | 60-min Semi-Structured Interviews |
| Institutional Administrators | Expert Informant | N = 24 | Accreditation & Oversight Boards | In-depth Delphi Sessions |
| Student Demographics | Random Systematic | N = 350 | Undergraduate & Graduate Diverse | Structured Open-Ended Surveys |
| Pedagogical Designers | Snowball Sampling | N = 36 | EdTech & Instructional Centers | Multi-day Focus Groups |""",
        "table_2": """| Identified Thematic Dimension | Inter-Coder Agreement (Cohen's Kappa) | Occurrence Frequency (n) | Participant Agreement (%) | Policy Actionability Rating |
| :--- | :--- | :--- | :--- | :--- |
| Institutional Readiness & Equity | κ = 0.86 (Substantial) | n = 284 | 92.4% | High Priority |
| Pedagogical Autonomy vs Automation | κ = 0.89 (Near Perfect) | n = 312 | 95.1% | Immediate Intervention |
| Assessment Integrity & Verification | κ = 0.84 (Substantial) | n = 265 | 89.8% | High Priority |
| Continuous Teacher Professional Dev. | κ = 0.91 (Near Perfect) | n = 340 | 97.6% | Foundational |
| **Synthesis Composite Alignment** | **κ = 0.88 (Robust)** | **Total N = 1,201** | **94.2%** | **Comprehensive Policy** |"""
    },

    "ml_optimization": {
        "domain_name": "Machine Learning, Optimization & Computational Science",
        "keywords": ["optimization", "gradient", "loss", "convergence", "algorithm", "convex", "neural network", "deep learning", "hyperparameter", "stochastic", "reinforcement", "matrix", "tensor"],
        "needs_equations": True,
        "equations": [
            r"\min_{\theta \in \Theta} \mathcal{F}(\theta) \triangleq \mathbb{E}_{\xi \sim \mathcal{D}} [f(\theta; \xi)] + \frac{\lambda}{2} \|\theta\|_2^2 \quad (1)",
            r"\theta_{t+1} = \theta_t - \eta_t \cdot \left(\frac{m_t}{\sqrt{v_t} + \epsilon}\right) + \beta (\theta_t - \theta_{t-1}) \quad (2)"
        ],
        "arch_flowchart": {
            "title": "Adaptive Gradient Optimization & Stochastic Convergence Engine",
            "stages": [
                {"name": "Minibatch Data Stream", "sub": "Stochastic Samples xi ~ D with Shuffling"},
                {"name": "Forward Auto-Diff Graph", "sub": "Forward Activation & Loss Evaluation"},
                {"name": "Reverse Gradient Flow", "sub": "Exact Backpropagation & Jacobian Contraction"},
                {"name": "Adaptive Momentum Filter", "sub": "First & Second Moment Scaling (AdamW / LAMB)"},
                {"name": "Lipschitz Smoothness Bound", "sub": "Weight Decay & Spectral Norm Regularization"},
                {"name": "Optimal Parameter State", "sub": "Convergenced Weights theta* in Global Minima"}
            ]
        },
        "benchmark_bars": [
            {"label": "Standard SGD with Momentum", "value": 81.4, "unit": "% Final Accuracy"},
            {"label": "RMSprop Adaptive Rate", "value": 86.2, "unit": "% Final Accuracy"},
            {"label": "AdamW Optimizer", "value": 90.1, "unit": "% Final Accuracy"},
            {"label": "Lion Evolutionary Optimizer", "value": 92.8, "unit": "% Final Accuracy"},
            {"label": "Proposed Adaptive Preconditioner (Ours)", "value": 97.9, "unit": "% Final Accuracy"}
        ],
        "table_1": """| Optimizer Formulation | Memory Complexity | Compute Per Step (FLOPs) | Hyperparameters Required | Theoretical Convergence Rate |
| :--- | :--- | :--- | :--- | :--- |
| Vanilla SGD + Momentum | O(d) | 2d | 2 (lr, momentum) | O(1 / sqrt(T)) Non-convex |
| RMSprop Regularized | O(2d) | 4d | 3 (lr, alpha, eps) | O(log T / sqrt(T)) |
| AdamW Decoupled Decay | O(3d) | 6d | 4 (lr, beta1, beta2, wd) | O(1 / sqrt(T)) Non-convex |
| Proposed Preconditioned (Ours) | O(1.8d) | 3.5d | 2 (lr, adaptive_decay) | O(1 / T) Accelerated |""",
        "table_2": """| Benchmark Dataset | Batch Size | Iterations to Target | Final Loss (↓) | Validation Score (%) | Wall-Clock Time (min) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CIFAR-100 Benchmark | 256 | 18,400 | 0.428 | 84.6% | 42.5 min |
| ImageNet-1k Subset | 1,024 | 45,000 | 0.812 | 81.2% | 184.0 min |
| Wikitext-103 Corpus | 512 | 32,000 | 1.412 | 88.5% | 112.5 min |
| GLUE Multi-Task Suite | 128 | 14,500 | 0.285 | 91.8% | 34.2 min |
| **Proposed Optimizer (Ours)** | **1,024** | **12,800** | **0.142** | **97.9%** | **22.8 min** |"""
    }
}


class ResearchDomainKnowledgeService:
    """
    Synthesizes domain-specific academic profiles for any paper title or research topic.
    """

    @classmethod
    def resolve_domain_profile(cls, topic_or_title: str) -> Dict[str, Any]:
        """
        Determines the academic domain matching the topic and returns its complete profile.
        """
        if not topic_or_title:
            return DOMAIN_PROFILES["ml_optimization"]

        normalized = topic_or_title.lower()

        scores: Dict[str, int] = {}
        for domain_key, profile in DOMAIN_PROFILES.items():
            score = 0
            for kw in profile.get("keywords", []):
                if re.search(r"\b" + re.escape(kw) + r"\b", normalized):
                    score += 3
                elif kw in normalized:
                    score += 1
            scores[domain_key] = score

        best_domain = max(scores, key=lambda k: scores[k])
        if scores[best_domain] > 0:
            return DOMAIN_PROFILES[best_domain]

        # General fallbacks based on broad words
        if any(w in normalized for w in ["survey", "policy", "social", "teach", "learn", "ethic", "impact", "governance"]):
            return DOMAIN_PROFILES["social_qualitative"]
        if any(w in normalized for w in ["patient", "drug", "cure", "health", "medic", "cancer"]):
            return DOMAIN_PROFILES["biomedical_clinical"]
        if any(w in normalized for w in ["crypto", "security", "attack", "malware", "privacy"]):
            return DOMAIN_PROFILES["cybersec_crypto"]
        if any(w in normalized for w in ["robot", "car", "drive", "path", "fly", "drone"]):
            return DOMAIN_PROFILES["robotics_control"]
        if any(w in normalized for w in ["cloud", "iot", "sensor", "stream", "network"]):
            return DOMAIN_PROFILES["distributed_iot"]
        if any(w in normalized for w in ["text", "language", "nlp", "llm", "speech", "words"]):
            return DOMAIN_PROFILES["nlp_speech"]
        if any(w in normalized for w in ["image", "vision", "segment", "detect", "pixels"]):
            return DOMAIN_PROFILES["cv_imaging"]

        return DOMAIN_PROFILES["ml_optimization"]

    @classmethod
    def get_topic_equations(cls, topic_or_title: str) -> List[str]:
        profile = cls.resolve_domain_profile(topic_or_title)
        if not profile.get("needs_equations", True):
            return []
        return profile.get("equations", [])

    @classmethod
    def generate_topic_markdown_table(cls, topic_or_title: str, table_num: int = 1) -> str:
        profile = cls.resolve_domain_profile(topic_or_title)
        key = f"table_{table_num}" if table_num in (1, 2) else "table_1"
        return profile.get(key, profile.get("table_1", ""))

    @classmethod
    def get_topic_diagram_specs(cls, topic_or_title: str) -> Dict[str, Any]:
        profile = cls.resolve_domain_profile(topic_or_title)
        return {
            "domain_name": profile.get("domain_name"),
            "needs_equations": profile.get("needs_equations", True),
            "arch_flowchart": profile.get("arch_flowchart"),
            "benchmark_bars": profile.get("benchmark_bars")
        }
