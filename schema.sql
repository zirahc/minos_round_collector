-- One row per Minos round. Run in the Supabase SQL editor.
-- Rank-1 scoring is flattened. Reveal file URLs stay in files (jsonb).

create table if not exists public.rounds (
    round_id text primary key,
    status text,
    region text,
    window_id text,
    selected_position integer,

    draw_block_height bigint,
    draw_block_hash text,

    file_hash_bam text,
    file_hash_truth_vcf text,
    file_hash_mutations_vcf text,
    files jsonb not null default '[]'::jsonb,

    chain_network text,
    chain_netuid integer,

    start_time timestamptz,
    submission_end_time timestamptz,
    scoring_end_time timestamptz,
    score_finalization_time timestamptz,

    submission_count integer,
    scored_count integer,
    score_count integer,
    identity_revealed boolean,
    is_finalized boolean,

    rank_1_hotkey text,
    rank_1_uid integer,
    rank_1_tool_name text,
    rank_1_config_hash text,
    rank_1_status text,
    rank_1_combined_final double precision,
    rank_1_snp_final double precision,
    rank_1_indel_final double precision,
    rank_1_weight double precision,
    rank_1_incentive double precision,
    rank_1_emission double precision,
    rank_1_eligible boolean,
    rank_1_participation_count integer,
    rank_1_validator_count integer,
    rank_1_submitted_at timestamptz,
    rank_1_scored_at timestamptz,

    huggingface text,
    inserted_at timestamptz not null default now()
);

create index if not exists rounds_start_time_idx on public.rounds (start_time desc);
create index if not exists rounds_rank_1_hotkey_idx on public.rounds (rank_1_hotkey);

alter table public.rounds add column if not exists huggingface text;

alter table public.rounds enable row level security;
