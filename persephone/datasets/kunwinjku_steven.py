""" Interface to Steven's Kunwinjku data. """

import glob
import os
from os.path import join
from pathlib import Path
import sys
from typing import List, NamedTuple, Set

from pympi.Elan import Eaf

import persephone.corpus
from .. import config
from ..transcription_preprocessing import segment_into_tokens

Utterance = NamedTuple("Utterance", [("file", str),
                                     ("start_time", int),
                                     ("end_time", int),
                                     ("text", str)])

BASIC_PHONEMES = set(["a", "b", "d", "dj", "rd", "e", "h", "i", "k", "l",
            "rl", "m", "n", "ng", "nj", "rn", "o", "r", "rr", "u",
            "w", "y",])
DOUBLE_STOPS = set(["bb", "dd", "djdj", "rdd", "kk"])
DIPHTHONGS = set(["ay", "aw", "ey", "ew", "iw", "oy", "ow", "uy"])
PHONEMES = BASIC_PHONEMES | DOUBLE_STOPS | DIPHTHONGS

def get_en_words() -> Set[str]:
    """
    Returns a list of English words which can be used to filter out
    code-switched sentences.
    """

    with open(config.EN_WORDS_PATH) as words_f:
        raw_words = words_f.readlines()
    en_words = set([word.strip().lower() for word in raw_words])
    NA_WORDS_IN_EN_DICT = set(["kore", "nani", "karri", "imi", "o", "yaw", "i",
                           "bi", "aye", "imi", "ane", "kubba", "kab", "a-",
                           "ad", "a", "mak", "selim", "ngai", "en", "yo",
                           "wud", "mani", "yak", "manu", "ka-", "mong",
                           "manga", "ka-", "mane", "kala", "name", "kayo",
                           "kare", "laik", "bale", "ni", "rey", "bu",
                           "re", "real", "iman", "bom", "wam",
                           "alu", "nan", "kure", "kuri", "wam", "ka", "ng",
                           "yi", "na", "m", "arri", "e", "kele", "arri", "nga",
                           "kakan", "ai", "ning", "mala", "ti", "wolk",
                           "bo", "andi", "ken", "ba", "aa", "kun", "bini",
                           "wo", "bim", "man", "bord", "al", "mah", "won",
                           "ku", "ay", "belen", "dye", "wen", "yah", "muni",
                           "bah", "di", "mm", "anu", "nane", "ma", "kum",
                           "birri", "ray", "h", "kane", "mumu", "bi", "ah",
                           "i-", "n", "mi",
                           ])
    EN_WORDS_NOT_IN_EN_DICT = set(["screenprinting"])
    en_words = en_words.difference(NA_WORDS_IN_EN_DICT)
    en_words = en_words | EN_WORDS_NOT_IN_EN_DICT
    return en_words

EN_WORDS = get_en_words()

def good_elan_paths(org_dir: str = config.KUNWINJKU_STEVEN_DIR) -> List[str]:
    """
    Returns a list of ELAN files for recordings with good quality audio, as
    designated by Steven.
    """

    with open(join(org_dir, "good-files.txt")) as path_list:
        good_paths = [path.strip() for path in path_list]

    elan_paths = []
    for path in good_paths:
        _, ext = os.path.splitext(path)
        if ext == ".eaf":
            elan_paths.append(join(org_dir, path))
        else:
            full_path = join(org_dir, path)
            if os.path.isdir(full_path):
                for elan_path in glob.glob('{}/**/*.eaf'.format(full_path),
                                           recursive=True):
                    elan_paths.append(elan_path)

    return elan_paths

def explore_elan_files(elan_paths):
    """
    A function to explore the tiers of ELAN files.
    """

    for elan_path in elan_paths:
        print(elan_path)
        eafob = Eaf(elan_path)
        tier_names = eafob.get_tier_names()
        for tier in tier_names:
            print("\t", tier)
            try:
                for annotation in eafob.get_annotation_data_for_tier(tier):
                    print("\t\t", annotation)
            except KeyError:
                continue

        input()

def elan_utterances(org_dir: str = config.KUNWINJKU_STEVEN_DIR) -> List[Utterance]:
    """ Collects utterances from various ELAN tiers. This is based on analysis
    of hte 'good' ELAN files, and may not generalize."""

    elan_tiers = {"rf", "rf@RN", "rf@MARK",
                  "xv", "xv@RN", "xv@MN", "xv@JN", "xv@EN", "xv@MARK", "xv@GN",
                  "nt@RN", "nt@JN",
                  "PRN_free", "PRN_Pfx", "NmCl_Gen", "ng_DROP",
                  "Other",
                 }

    utterances = []
    for elan_path in good_elan_paths(org_dir=org_dir):
        eafob = Eaf(elan_path)
        #import pprint; pprint.pprint(dir(eafob))
        can_find_path = False
        for md in eafob.media_descriptors:
            try:
                media_path = os.path.join(os.path.dirname(elan_path),
                                          md["RELATIVE_MEDIA_URL"])
                if os.path.exists(media_path):
                    # Only one media_path file is needed, as long as it exists.
                    can_find_path = True
                    break
                # Try just looking for the basename specified in the
                # RELATIVE_MEDIA_URL
                media_path = os.path.join(os.path.dirname(elan_path),
                                          os.path.basename(md["RELATIVE_MEDIA_URL"]))
                if os.path.exists(media_path):
                    can_find_path = True
                    break
            except KeyError:
                # Then it might be hard to find the MEDIA URL if its not
                # relative. Keep trying.
                continue
        if can_find_path:
            tier_names = eafob.get_tier_names()
            for tier in tier_names:
                if tier.startswith("rf") or tier.startswith("xv") or tier in elan_tiers:
                    for annotation in eafob.get_annotation_data_for_tier(tier):
                        utterance = Utterance(media_path, *annotation[:3])
                        if not utterance.text.strip() == "":
                            utterances.append(utterance)
        else:
            print("Warning: Can't find the media file for {}".format(elan_path))

    return utterances

def segment_phonemes(text: str, phoneme_inventory: Set[str] = PHONEMES) -> str:
    """
    Takes as input a string in Kunwinjku and segments it into phoneme-like
    units based on the standard orthographic rules specified at
    http://bininjgunwok.org.au/
    """

    text = text.lower()
    text = segment_into_tokens(text, phoneme_inventory)
    return text

def explore_code_switching(f=sys.stdout):

    import spacy
    nlp = spacy.load("xx")

    utters = elan_utterances()

    en_count = 0
    for i, utter in enumerate(utters):
        toks = nlp(utter.text)
        words = [tok.lower_ for tok in toks if not tok.is_punct]
        for word in words:
            if word in EN_WORDS:
                en_count += 1
                print("Utterance #%s" % i, file=f)
                print("Original: %s" % utter.text, file=f)
                print("Tokenized: %s" % words, file=f)
                print("Phonemic: %s" % segment_phonemes(utter.text), file=f)
                print("En word: %s" % word, file=f)
                print("---------------------------------------------", file=f)
                break
    print(en_count)
    print(len(utters))

class Corpus(persephone.corpus.Corpus):
    def __init__(feat_type="fbank", label_type="phonemes"):

        tgt_dir = Path(config.TGT_DIR)
        wav_dir = p / "wav"
        label_dir = p / "label"
        print(label_dir)

        if label_type == "phonemes":
            labels = PHONEMES
        else:
            raise NotImplementedError(
                "label_type {} not implemented.".format(label_type))

        # 0. Fetch the utterances from the ELAN files

        # 1. Preprocess transcriptions and put them in the label/ directory

        # 2. Split the WAV files and put them in the wav/

        super().__init__(feat_type, label_type, tgt_dir, labels)
