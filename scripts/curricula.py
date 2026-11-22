"""Staff-curated syllabi. Lowercase keys refer to the shared topic catalogue."""

# Course, level, learning objectives, and ordered modules.
CURRICULA = (
    ("Machine Learning", "Intermediate", (
        "Prepare data and establish defensible baselines.", "Evaluate supervised and unsupervised models.",
        "Deploy and monitor a reproducible prediction service.",
    ), (
        ("Programming and mathematics", "python; numpy; linear; probability; stats; optimization"),
        ("Data and evaluation", "ml; Data Cleaning and Feature Engineering; evaluation; Cross-Validation and Data Leakage"),
        ("Supervised models", "supervised; Linear Regression; Logistic Regression; Decision Trees; Ensemble Methods; Support Vector Machines"),
        ("Unsupervised and advanced models", "unsupervised; Clustering; Dimensionality Reduction; nn; dl"),
        ("Production and capstone", "Production Systems; Model Monitoring; Machine Learning Capstone"),
    )),
    ("Artificial Intelligence", "Intermediate", ("Compare search, inference, and decision methods.", "Evaluate agent behavior under uncertainty."), (
        ("Agents and search", "python; Intelligent Agents; Heuristic Search; Adversarial Search; Constraint Satisfaction"),
        ("Reasoning", "probability; Knowledge Representation; Logical Inference; Probabilistic Reasoning"),
        ("Decisions", "Planning; Decision Theory; AI Evaluation Project"),
    )),
    ("Deep Learning", "Advanced", ("Train neural networks and diagnose generalization.", "Evaluate vision and language architectures."), (
        ("Foundations", "python; numpy; linear; optimization; nn; dl"),
        ("Architectures", "Convolutional Networks; Sequence Models; Attention and Transformers; Generative Models"),
        ("Experiments", "Regularization and Training Diagnostics; Transfer Learning; Deep Learning Project"),
    )),
    ("Data Science", "Intermediate", ("Build reliable data analysis workflows.", "Communicate uncertainty and evidence."), (
        ("Data preparation", "python; numpy; Tabular Data Wrangling; Missing Data"),
        ("Exploration and inference", "visualization; probability; stats; Experimental Design"),
        ("Applied analysis", "Data Mining; Reproducible Reporting; Data Science Project"),
    )),
    ("Python", "Beginner", ("Write, test, and package a Python program.", "Select effective data structures and interfaces."), (
        ("Language essentials", "python; Python Collections; Control Flow and Iteration; File I/O and Exceptions"),
        ("Software construction", "Python Modules; Classes and Protocols; Testing Python Code"),
        ("Application", "Python Packaging; Python Application Project"),
    )),
    ("Database Management Systems", "Intermediate", ("Design normalized relational schemas.", "Use transactions and indexes to maintain data integrity."), (
        ("Relational foundations", "relational; sql; sql_joins; normalization"),
        ("Database internals", "Indexes and Access Paths; Query Optimization; transactions; Recovery and Logging"),
        ("Applied database design", "Distributed Databases; Database Design Project"),
    )),
    ("Data Structures and Algorithms", "Intermediate", ("Analyze time and space tradeoffs.", "Design and justify algorithms for concrete problems."), (
        ("Data structures", "python; ds; complexity; Hash Tables; Balanced Trees; Heaps"),
        ("Algorithm design", "algorithms; Greedy Algorithms; Dynamic Programming; graphs"),
        ("Applied analysis", "Shortest Paths; Algorithm Design Project"),
    )),
    ("Operating Systems", "Intermediate", ("Trace process, memory, and file-system behavior.", "Explain synchronization and deadlock prevention."), (
        ("Processes", "os; processes; Synchronization; Deadlocks"),
        ("Memory and storage", "memory; File Systems; Storage and I/O"),
        ("Systems practice", "Virtualization; Systems Measurement Project"),
    )),
    ("Computer Networks", "Intermediate", ("Trace traffic across the network stack.", "Diagnose routing and transport behavior."), (
        ("Layering and links", "Network Layering; Ethernet and Switching"),
        ("Internet and transport", "IP Addressing; Routing; UDP and TCP; Congestion Control"),
        ("Applications", "DNS and HTTP; Network Security Fundamentals; Packet Analysis Project"),
    )),
    ("Natural Language Processing", "Advanced", ("Build baseline text models and evaluate them.", "Compare representations and transformer models."), (
        ("Text representations", "python; text; nlp; N-Gram Models; Word Embeddings"),
        ("Modeling", "Text Classification; Sequence Labeling; Transformer Language Models"),
        ("Evaluation", "Retrieval and Ranking; NLP Evaluation Project"),
    )),
    ("MLOps", "Advanced", ("Build repeatable model release workflows.", "Monitor and roll back a model deployment."), (
        ("Model lifecycle", "ml; evaluation; Data and Model Versioning; Experiment Tracking"),
        ("Delivery", "Pipeline Orchestration; Model Serving; CI and CD for ML"),
        ("Reliability", "Model Drift and Alerts; Governance and Rollbacks; MLOps Project"),
    )),
    ("Software Engineering", "Intermediate", ("Translate requirements into testable designs.", "Maintain software through a release cycle."), (
        ("Planning", "Requirements Engineering; Design Modeling"),
        ("Building", "Software Architecture; Design Patterns; Software Testing; Refactoring"),
        ("Delivery", "Version Control; Release Engineering; Software Engineering Project"),
    )),
    ("Reinforcement Learning", "Advanced", ("Model sequential decisions and expected return.", "Compare planning and learning approaches."), (
        ("Foundations", "probability; Bandits; Markov Decision Processes; Bellman Equations"),
        ("Learning methods", "Dynamic Programming for Control; Monte Carlo Methods; Temporal Difference Learning; Policy Gradients"),
        ("Applied learning", "Deep Reinforcement Learning; Reinforcement Learning Project"),
    )),
    ("Mathematics and Statistics", "Intermediate", ("Apply linear algebra, probability and inference.", "Use optimization to fit and assess models."), (
        ("Linear algebra", "linear; Matrix Decompositions; Vector Calculus; optimization"),
        ("Probability and inference", "probability; stats; Bayesian Inference; Regression and Uncertainty"),
        ("Applied modeling", "Sampling and Simulation; Statistical Modeling Project"),
    )),
)

TOPIC_OBJECTIVES = {
    "Data Cleaning and Feature Engineering": "Construct a repeatable transformation pipeline for missing values, encodings and scaling.",
    "Cross-Validation and Data Leakage": "Use time-aware or stratified validation and isolate transformations from evaluation data.",
    "Linear Regression": "Fit a linear model, interpret residuals and compare regularized variants.",
    "Logistic Regression": "Estimate class probabilities and select an operating threshold.",
    "Decision Trees": "Compare splits, depth and pruning on held-out data.",
    "Ensemble Methods": "Compare bagging, random forests and boosted trees on the same metrics.",
    "Support Vector Machines": "Explain the margin and compare linear and nonlinear kernels.",
    "Clustering": "Compare centroid-based and density-based methods and evaluate stability.",
    "Dimensionality Reduction": "Project data with PCA and assess the tradeoff between compression and variance.",
    "Production Systems": "Package preprocessing and inference, define a service contract and plan staged rollout.",
    "Model Monitoring": "Define service and data-quality metrics, drift checks, and rollback criteria.",
    "Machine Learning Capstone": "Train a baseline and a challenger, document their evaluation, and ship a monitored inference demo.",
}
