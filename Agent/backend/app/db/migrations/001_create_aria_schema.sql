CREATE SCHEMA IF NOT EXISTS aria;

-- users
CREATE TABLE aria.users (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email       VARCHAR(255) NOT NULL UNIQUE,
    full_name   VARCHAR(120) NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- chat_messages  <- ChatMessage
CREATE TABLE aria.chat_messages (
    id                 VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id            VARCHAR(36) NOT NULL REFERENCES aria.users(id) ON DELETE CASCADE,
    role               VARCHAR(20) NOT NULL,
    content            TEXT        NOT NULL,
    detected_language  VARCHAR(10),
    intent             VARCHAR(50),
    latency_ms         INTEGER,
    sources            JSONB       DEFAULT '[]'::jsonb,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);


-- agent_tool_executions  <- ActionSummary
CREATE TABLE aria.agent_tool_executions (
    id                 VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    message_id         VARCHAR(36)  REFERENCES aria.chat_messages(id) ON DELETE CASCADE,
    tool_name          VARCHAR(100) NOT NULL,
    parameters         JSONB        DEFAULT '{}'::jsonb,
    result_summary     TEXT,
    execution_time_ms  INTEGER,
    created_at         TIMESTAMPTZ  DEFAULT NOW()
);


-- study_plans  <- PlannerOutput & StudyPlan
CREATE TABLE aria.study_plans (
    id                      VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id                 VARCHAR(36)  NOT NULL REFERENCES aria.users(id) ON DELETE CASCADE,
    topic                   VARCHAR(255) NOT NULL,
    tone_applied            VARCHAR(50),
    direct_answer           TEXT,
    analogy_or_intuition    TEXT,
    total_duration_minutes  INTEGER,
    created_at              TIMESTAMPTZ  DEFAULT NOW()
);


-- study_plan_phases  <- StudyPhase
CREATE TABLE aria.study_plan_phases (
    id                VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    plan_id           VARCHAR(36)  NOT NULL REFERENCES aria.study_plans(id) ON DELETE CASCADE,
    phase_number      INTEGER      NOT NULL,
    phase_name        VARCHAR(255) NOT NULL,
    duration_minutes  INTEGER,
    description       TEXT,
    key_focus         TEXT,
    UNIQUE (plan_id, phase_number)
);


-- flashcards  <- Flashcard
CREATE TABLE aria.flashcards (
    id          VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id     VARCHAR(36)  NOT NULL REFERENCES aria.users(id) ON DELETE CASCADE,
    card_id     VARCHAR(50),
    topic       VARCHAR(255),
    front       TEXT         NOT NULL,
    back        TEXT         NOT NULL,
    difficulty  VARCHAR(20),
    format      VARCHAR(30),
    key_points  JSONB        DEFAULT '[]'::jsonb,
    tags        TEXT[]       DEFAULT '{}',
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);


-- quiz_questions  <- QuizQuestion
CREATE TABLE aria.quiz_questions (
    id                    VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id               VARCHAR(36) NOT NULL REFERENCES aria.users(id) ON DELETE CASCADE,
    question_order        INTEGER     NOT NULL,
    question_text         TEXT        NOT NULL,
    options               JSONB       NOT NULL,
    correct_answer        TEXT        NOT NULL,
    correct_option_index  INTEGER,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);



-- study_flowcharts  <- FlowchartResult
CREATE TABLE aria.study_flowcharts (
    id                 VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id            VARCHAR(36)  NOT NULL REFERENCES aria.users(id) ON DELETE CASCADE,
    topic              VARCHAR(255),
    title              VARCHAR(255),
    mermaid_markdown   TEXT         NOT NULL,
    nodes              JSONB        DEFAULT '[]'::jsonb,
    edges              JSONB        DEFAULT '[]'::jsonb,
    steps_walkthrough  JSONB        DEFAULT '[]'::jsonb,
    created_at         TIMESTAMPTZ  DEFAULT NOW()
);


-- indexes on foreign keys
CREATE INDEX idx_chat_messages_user   ON aria.chat_messages(user_id);
CREATE INDEX idx_tool_exec_message    ON aria.agent_tool_executions(message_id);
CREATE INDEX idx_study_plans_user     ON aria.study_plans(user_id);
CREATE INDEX idx_plan_phases_plan     ON aria.study_plan_phases(plan_id);
CREATE INDEX idx_flashcards_user      ON aria.flashcards(user_id);
CREATE INDEX idx_quiz_questions_user  ON aria.quiz_questions(user_id);
CREATE INDEX idx_flowcharts_user      ON aria.study_flowcharts(user_id);


SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'aria'
ORDER BY table_name;