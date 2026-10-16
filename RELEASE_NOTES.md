# Darkest Dungeon PS Vita 한글패치 v0.9.1

PCSG01154용 rePatch 한국어 패치입니다.

## 0.9.1 변경 사항

- 전투 피해·스트레스 수치와 상태 문구에 필요한 영문·숫자 글리프를 한글 글꼴에 추가했습니다.
- 전투 표시 색상을 조정해 어두운 배경과 붉은 피격 효과 위에서 읽기 쉽게 했습니다.
- 두꺼운 전투 표시용 글꼴의 획을 얇게 조정했고, 실기에서 확인했습니다.

## 설치

1. 릴리스의 `patch_tools_v0.9.1.zip`을 PC의 폴더에 풀고, 같은 폴더에 `patch_sources_v0.9.1.tar`를 둡니다. TAR은 직접 풀 필요가 없습니다.
2. 본인 Vita판 PCSG01154의 원본 `content.psarc`를 준비하고 `python apply_patch_data.py --vita "D:\path\content.psarc"`를 실행합니다. Switch 원본은 필요하지 않습니다.
3. 생성된 `dist/v0.9.1/rePatch` 폴더를 Vita의 `ux0:`에 복사합니다. 기존 `ux0:rePatch/PCSG01154`가 있다면 먼저 백업합니다.
4. `ux0:rePatch/PCSG01154/content.psarc`가 있는지 확인한 뒤 게임을 실행합니다.

한국어 표시와 띄어쓰기, 전투 숫자 및 상태 문구의 표시는 실기에서 확인했습니다. 작은 설명 글자는 다소 흐릿할 수 있으며 전체 플레이와 DLC는 아직 확인하지 않았습니다.

빌드 방법, 복구 방법과 제작 출처는 저장소 README를 참고해 주세요.

