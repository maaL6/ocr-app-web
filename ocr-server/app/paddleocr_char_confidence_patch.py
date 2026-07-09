import numpy as np


DEFAULT_CHAR_CANDIDATE_TOP_K = 10


class CharConfidenceScore(float):
    """Float line score carrying decoded per-character metadata."""

    def __new__(cls, value, char_confidences=None, char_candidates=None):
        obj = float.__new__(cls, value)
        obj.char_confidences = [
            float(item) for item in (char_confidences or [])
        ]
        obj.char_candidates = [
            [
                {
                    "char": str(candidate["char"]),
                    "confidence": float(candidate["confidence"]),
                }
                for candidate in candidates
            ]
            for candidates in (char_candidates or [])
        ]
        return obj


def _top_char_candidates(probabilities, characters, ignored_tokens, top_k):
    if top_k <= 0:
        return []

    scores = np.asarray(probabilities, dtype="float32")
    if scores.ndim != 1:
        return []
    if len(scores) == 0:
        return []

    ignored_tokens = set(int(token) for token in ignored_tokens)
    pool_size = min(len(scores), top_k + len(ignored_tokens))
    top_ids = np.argpartition(scores, -pool_size)[-pool_size:]
    top_ids = top_ids[np.argsort(scores[top_ids])[::-1]]

    candidates = []
    for text_id in top_ids:
        text_id = int(text_id)
        if text_id in ignored_tokens or text_id >= len(characters):
            continue

        candidates.append({
            "char": str(characters[text_id]),
            "confidence": float(scores[text_id]),
        })
        if len(candidates) >= top_k:
            break

    return candidates


def apply_paddleocr_char_confidence_patch():
    """Keep PaddleOCR's line score behavior and expose decoder char metadata.

    PaddleOCR/PaddleX already computes per-character probabilities inside
    BaseRecLabelDecode.decode() as conf_list, but the public OCR pipeline only
    returns np.mean(conf_list) as rec_score. This patch preserves rec_score as a
    float-compatible value while attaching the original conf_list so the FastAPI
    response can publish per_char_confidences without inventing them. It also
    catches top-k character candidates before CTC reduces the full probability
    matrix to argmax indexes.
    """
    from paddlex.inference.models.text_recognition.processors import (
        BaseRecLabelDecode,
        CTCLabelDecode,
    )

    base_decode_patched = getattr(
        BaseRecLabelDecode.decode, "_char_confidence_patched", False
    )
    ctc_call_patched = getattr(
        CTCLabelDecode.__call__, "_char_confidence_patched", False
    )
    if base_decode_patched and ctc_call_patched:
        return

    def decode(
        self,
        text_index,
        text_prob=None,
        is_remove_duplicate=False,
        return_word_box=False,
        text_candidates=None,
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

            if text_candidates is not None:
                candidate_list = [
                    text_candidates[batch_idx][idx]
                    for idx in np.where(selection == True)[0]
                ]
            else:
                candidate_list = [[] for _ in char_list]

            text = "".join(char_list)
            if self.reverse:
                text = self.pred_reverse(text)
                conf_list = list(reversed(conf_list))
                candidate_list = list(reversed(candidate_list))

            line_confidence = CharConfidenceScore(
                float(np.mean(conf_list)), conf_list, candidate_list
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

    def ctc_call(self, pred, return_word_box=False, **kwargs):
        preds = np.array(pred[0])
        preds_idx = preds.argmax(axis=-1)
        preds_prob = preds.max(axis=-1)
        ignored_tokens = self.get_ignored_tokens()
        text_candidates = [
            [
                _top_char_candidates(
                    timestep_prob,
                    self.character,
                    ignored_tokens,
                    DEFAULT_CHAR_CANDIDATE_TOP_K,
                )
                for timestep_prob in row
            ]
            for row in preds
        ]
        text = self.decode(
            preds_idx,
            preds_prob,
            text_candidates=text_candidates,
            is_remove_duplicate=True,
            return_word_box=return_word_box,
        )
        if return_word_box:
            for rec_idx, rec in enumerate(text):
                wh_ratio = kwargs["wh_ratio_list"][rec_idx]
                max_wh_ratio = kwargs["max_wh_ratio"]
                rec[2][0] = rec[2][0] * (wh_ratio / max_wh_ratio)
        texts = []
        scores = []
        for t in text:
            texts.append(t[0] if len(t) <= 2 else (t[0], t[2]))
            scores.append(t[1])
        return texts, scores

    if not base_decode_patched:
        decode._char_confidence_patched = True
        BaseRecLabelDecode.decode = decode
    if not ctc_call_patched:
        ctc_call._char_confidence_patched = True
        CTCLabelDecode.__call__ = ctc_call
