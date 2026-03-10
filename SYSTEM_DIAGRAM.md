flowchart TD
    A[Android App<br/>Dark UI / Board / Training / Deep Chat / Profile]
    A1[Quick Coach Mode]
    A2[Deep Chess Chat Mode]
    A3[Game Review / Training Flow]
    A4[Profile / Progress]

    A --> A1
    A --> A2
    A --> A3
    A --> A4

    A --> B[API / Server Layer]

    B --> B1[Request Validation]
    B --> B2[Auth Check]
    B --> B3[Routing / Response Contracts]

    B --> C[Core Server Pipeline]

    C --> C1[Request Normalization]
    C --> C2[Game / Position Processing]
    C --> C3[Pipeline Orchestration]

    C --> D[Engine Layer]
    C --> E[Intelligence Layer]
    C --> F[Data Layer]
    C --> G[SECA Architecture]
    C --> H[Monitoring / Observability]

    subgraph D1[Engine Layer]
        D --> D2[Engine Pool]
        D --> D3[UCI Controller]
        D --> D4[JNI Bridge]
        D --> D5[Evaluation Cache]
        D --> D6[Result Normalization]
    end

    subgraph E1[Intelligence Layer]
        E --> E2[Coaching Logic]
        E --> E3[RAG Context Builder]
        E --> E4[LLM Modules]
        E --> E5[Recommendation Logic]
        E --> E6[Schema Validation]
    end

    subgraph F1[Data Layer]
        F --> F2[Users / Auth Data]
        F --> F3[Games / Moves]
        F --> F4[Engine Evaluations]
        F --> F5[Coaching Outputs]
        F --> F6[Player Profiles]
        F --> F7[Training History]
        F --> F8[Analytics Storage]
        F --> F9[Event Store]
    end

    subgraph G1[SECA]
        G --> G2[SECA Auth]
        G --> G3[SECA Events]
        G --> G4[SECA Brain]
        G --> G5[SECA Analytics]
        G --> G6[SECA Safety]
        G --> G7[SECA Evaluation Governance]
    end

    subgraph H1[Monitoring]
        H --> H2[Health Checks]
        H --> H3[Latency Metrics]
        H --> H4[Logs / Traces]
        H --> H5[Error Tracking]
    end

    D --> E
    F --> E
    G --> E
    E --> F
    E --> H
    G --> H

    D4 -. critical validation .-> A
    D5 -. repeated positions .-> C
    E3 --> E4
    E4 --> E6
    E6 --> B

    G4 --> E2
    G5 --> E5
    G3 --> F9
    G2 --> B2

    F6 --> E3
    F7 --> E3
    F8 --> G5

    B --> A
