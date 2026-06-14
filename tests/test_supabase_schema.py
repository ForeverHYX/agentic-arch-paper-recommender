from pathlib import Path
import unittest


class SupabaseSchemaTests(unittest.TestCase):
    def test_schema_defines_feedback_and_recommendation_tables_with_rls(self):
        schema = Path("supabase/schema.sql").read_text(encoding="utf-8").lower()

        self.assertIn("create table if not exists public.feedback_events", schema)
        self.assertIn("create table if not exists public.recommendation_runs", schema)
        self.assertIn("create table if not exists public.profile_state", schema)
        self.assertIn("paper_id text not null", schema)
        self.assertIn("item_type text not null default 'paper'", schema)
        self.assertIn("repository_url text", schema)
        self.assertIn("paper_links jsonb not null default '[]'::jsonb", schema)
        self.assertIn("rating text not null", schema)
        self.assertIn("affiliations jsonb not null default '[]'::jsonb", schema)
        self.assertIn("liked_affiliations jsonb not null default '[]'::jsonb", schema)
        self.assertIn("disliked_affiliations jsonb not null default '[]'::jsonb", schema)
        self.assertIn("liked_toolchains jsonb not null default '[]'::jsonb", schema)
        self.assertIn("disliked_toolchains jsonb not null default '[]'::jsonb", schema)
        self.assertIn("affiliation_weights jsonb not null default '{}'::jsonb", schema)
        self.assertIn("toolchain_weights jsonb not null default '{}'::jsonb", schema)
        self.assertIn("check (rating in ('like', 'dislike'))", schema)
        self.assertIn("alter table public.feedback_events enable row level security", schema)
        self.assertIn("create policy feedback_events_public_insert", schema)
        self.assertIn("for insert", schema)


if __name__ == "__main__":
    unittest.main()
