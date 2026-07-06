import numpy as np


class CharConfidenceScore(float):
    """Float line score carrying decoded per-character confidences."""

    def __new__(cls, value, char_confidences=None):
        obj = float.__new__(cls, value)
        obj.char_confidences = [
            float(item) for item in (char_confidences or [])
        ]
        return obj


def apply_paddleocr_char_confidence_patch():
    """Keep PaddleOCR's line score behavior and expose decoder char confidences.

    PaddleOCR/PaddleX already computes per-character probabilities inside
    BaseRecLabelDecode.decode() as conf_list, but the public OCR pipeline only
    returns np.mean(conf_list) as rec_score. This patch preserves rec_score as a
    float-compatible value while attaching the original conf_list so the FastAPI
    response can publish per_char_confidences without inventing them.
    """
    try:
        from paddlex.inference.models.text_recognition.processors import (
            BaseRecLabelDecode,
        )
    except ModuleNotFoundError:
        try:
            from paddleocr.ppocr.postprocess.rec_postprocess import (
                BaseRecLabelDecode,
            )
        except ModuleNotFoundError:
            print("[WARN] BaseRecLabelDecode not found. Cannot apply character confidence patch.")
            return

    if getattr(BaseRecLabelDecode.decode, "_char_confidence_patched", False):
        return

    def decode(
        self,
        text_index,
        text_prob=None,
        is_remove_duplicate=False,
        return_word_box=False,
    ):
        result_list = []
        ignored_tokens = self.get_ignored_tokens()
        batch_size = len(text_index)

        for batch_idx in range(batch_size):
            selection = np.ones(len(text_index[batch_idx]), dtype=bool)
            if is_remove_duplicate:
                selection[1:] = (
                    text_index[batch_idx][1:] != text_index[batch_idx][:-1]
                )
            for ignored_token in ignored_tokens:
                selection &= text_index[batch_idx] != ignored_token

            char_list = [
                self.character[text_id] for text_id in text_index[batch_idx][selection]
            ]
            if text_prob is not None:
                conf_list = np.asarray(
                    text_prob[batch_idx][selection], dtype="float32"
                ).tolist()
            else:
                conf_list = [1.0] * len(char_list)
            if len(conf_list) == 0:
                conf_list = [0.0]

            text = "".join(char_list)
            if self.reverse:
                text = self.pred_reverse(text)
                conf_list = list(reversed(conf_list))

            line_confidence = CharConfidenceScore(
                float(np.mean(conf_list)), conf_list
            )

            if return_word_box:
                word_list, word_col_list, state_list = self.get_word_info(
                    text, selection
                )
                result_list.append(
                    (
                        text,
                        line_confidence,
                        [
                            len(text_index[batch_idx]),
                            word_list,
                            word_col_list,
                            state_list,
                        ],
                    )
                )
            else:
                result_list.append((text, line_confidence))

        return result_list

    decode._char_confidence_patched = True
    BaseRecLabelDecode.decode = decode
