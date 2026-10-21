-- Non-destructive migration for versioned questionnaire/material/workflow settings.
-- Existing rows receive the legacy researcher-assisted v3 configuration.
ALTER TABLE studies ADD COLUMN IF NOT EXISTS config_json TEXT NOT NULL DEFAULT '{}';
UPDATE studies SET config_json = '{"instrument_id":"SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual","questionnaire_version":3,"material_set_version":3,"study_mode":"researcher_assisted","enable_prototype_stage":true}'
WHERE config_json IS NULL OR config_json = '' OR config_json = '{}';
