다음 블로그 글을 숏폼 설명 영상으로 만들기 위해 분석하세요.

[규칙]
- 원문에 있는 내용만 사용합니다. 추측·일반 상식으로 채우지 않습니다.
- facts 에는 숫자·가격·시간·장소·고유명사·단계 순서처럼 영상에서 절대 바뀌면 안 되는 사실을 원문 표기 그대로 넣습니다.
- visual_motif 는 모든 장면 그림에 반복해서 등장시킬 시각 요소 1개를 영어로 씁니다(예: "a small round-faced narrator character with glasses", "a coffee cup icon"). 사람이 등장하는 글이면 캐릭터, 아니면 주제를 상징하는 사물.

[출력] 설명 없이 JSON 만:
{
  "core_message": "이 글의 한 줄 핵심 (한국어, 40자 이내)",
  "key_points": ["핵심 내용 3~6개, 원문 순서대로"],
  "facts": ["원문 표기 그대로의 사실"],
  "audience": "이 영상을 볼 사람",
  "tone": "정보 전달 / 후기 / 튜토리얼 등",
  "visual_motif": "English, one short phrase"
}

제목: {title}

본문:
{text}
