# -*- coding: utf-8 -*-

#한글 단어를 초성, 중성 종성으로 분리해주는 모듈

__author__ = 'bkyoo'

hangul_base_code = 0xAC00
hangul_last_code = 0xD7A3
chosung_code = 588
joongsung_code = 28

hangul_chosung = ('ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ',
                  'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ' ,
                  'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ',
                  'ㅎ')

hangul_joongsung = ('ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ',
                    'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ',
                    'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ',
                    'ㅡ', 'ㅢ', 'ㅣ')

hangul_jongsung = (' ', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ',
                   'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ',
                   'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ',
                   'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ',
                   'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ')


#함수에서 나갈 때는 무조건 utf-8로
def dismantle_hangul_chr(hangul_chr):
    #unicode 값을 숫자로 바꿔준다
    hangul_code = ord(hangul_chr)
    hangul_chr_code = hangul_code - hangul_base_code

    #이 숫자 범위에 해당하는 한글 코드들은 초성 중성 종성을 가지고 있다.
    #종성이 없는 글자의 경우 종성이 없다는 의미를 가진 특정 값을 종성 값으로 갖는다
    if hangul_base_code <= hangul_code <= hangul_last_code:
        chosung_index, other_chr_info = divmod(hangul_chr_code, chosung_code)
        chosung = hangul_chosung[chosung_index]

        joongsung_index, other_chr_info = divmod(other_chr_info, joongsung_code)
        joongsung = hangul_joongsung[joongsung_index]

        jongsung = hangul_jongsung[other_chr_info]

        #종성이 없을 경우에는 초성과 중성만 반환한다.
        return (chosung, joongsung) if jongsung == ' ' else (chosung, joongsung, jongsung)

    else:
        if isinstance(hangul_chr, unicode):
            hangul_chr = hangul_chr.encode('utf-8')

        #utf-8의 경우 iterator에 의해 글자 정보가 분해되는 것을 방지하기 위해 튜플로 묶어준다.
        return hangul_chr,


def analyze_hangul_str(hangul_str):
    if not isinstance(hangul_str, unicode):
        try:
            hangul_str = hangul_str.decode('utf-8')
        except UnicodeDecodeError:
            return None

    return ''.join(dismantled_hangul_chr
                    for hangul_chr in hangul_str
                    for dismantled_hangul_chr in dismantle_hangul_chr(hangul_chr))