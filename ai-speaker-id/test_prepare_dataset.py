import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("prepare_dataset.py")
spec = importlib.util.spec_from_file_location("prepare_dataset", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DatasetPreparationTests(unittest.TestCase):
    def extract(self, text):
        return module.extract(text, "fixture-book", {})

    def test_named_speaker_after_speech_verb(self):
        rows, unresolved, candidates, _ = self.extract(
            "— Вот чего ты её вечно злишь? — с улыбкой поинтересовался Дима, стоящий рядом."
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["speaker"], "Дима")
        self.assertEqual(rows[0]["quote"], "Вот чего ты её вечно злишь?")
        self.assertEqual(len(unresolved), 0)

    def test_passive_female_voice_is_not_mistaken_for_vocative(self):
        rows, unresolved, candidates, _ = self.extract(
            "— Нико! Нико, мать твою! — раздался снаружи раздраженный женский голос."
        )
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["reason"], "passive_voice_without_named_speaker")
        self.assertNotIn("Нико", [x["name"] for x in candidates])

    def test_quoted_passive_voice_is_unresolved(self):
        rows, unresolved, _, _ = self.extract(
            "«Нико, добро пожаловать!» — раздался в голове приветливый женский голос."
        )
        self.assertEqual(rows, [])
        self.assertEqual(unresolved[0]["quote"], "Нико, добро пожаловать!")

    def test_mixed_case_ai_name_is_preserved(self):
        rows, unresolved, candidates, _ = self.extract(
            "«На две минуты и тридцать семь секунд», — тут же выдал отчет ИмИн."
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["speaker"], "ИмИн")
        self.assertEqual(candidates[0]["name"], "ИмИн")

    def test_same_voice_attribution_recognizes_character_name(self):
        rows, _, _, _ = self.extract(
            "— Зато вполне возможно общее потомство, — все тем же ровным голосом заявила лейтенант Самуру."
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["speaker"], "Самуру")

    def test_literal_escaped_newlines_are_split_into_paragraphs(self):
        paragraphs = module.paragraphs_of(
            "Начало.\\nПродолжение.\\n\\n— Привет! — сказал Дима."
        )
        self.assertEqual(len(paragraphs), 3)
        self.assertIn("Продолжение.", paragraphs[1])
        self.assertIn("Привет!", paragraphs[2])

    def test_explicit_first_person_alias_maps_to_protagonist(self):
        rows, unresolved, candidates, _ = module.extract(
            "— Не начинай, — буркнул я.",
            "fixture-book",
            {"я": "Нико"},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["speaker"], "Нико")
        self.assertEqual(candidates[0]["aliases"], ["я"])
        self.assertEqual(unresolved, [])

    def test_sentence_adverbs_are_not_speaker_names(self):
        rows, unresolved, candidates, _ = self.extract(
            "— Понятно. — ответила немного встрепенувшаяся ламия, которая начала говорить."
        )
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
