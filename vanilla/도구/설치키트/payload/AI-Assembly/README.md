# AI-Assembly

국회사무처 의정연수원 신임관리자 과정 · 생성형 AI 업무 활용(심화): Claude Code
**법률안 검토보고서 에이전트 설계 및 업무 자동화** · 2026. 10. 26.

**바로 열기: [강의자료(HTML)](https://parkjui92.github.io/AI-Assembly/slides/)**

## 1. 강의자료 · 2. 입법조사관용 MCP·API 도구 모음

이 사본(법제업무팀 설치키트)에는 넣지 않았다. 설치와 플러그인 동작에 쓰지 않기 때문이다. 원본 저장소 [parkjui92/AI-Assembly](https://github.com/parkjui92/AI-Assembly)의 `slides/`, `tools/`에서 본다.

## 3. 플러그인: 법률안 검토보고서 작성팀(bill-review)

검토설계 → 관문①(설계 판정) → 쟁점 승인 → 자료조사·조문 원장 → 집필 → 조문 대조 검문소 → 관문②(초안 검수) → 한글(.hwpx) 변환

이 사본(`0.1.0-vanilla.1`)은 법제업무팀 저장소의 설치키트(`도구/설치키트/`)로 설치한다. 아래는 원본 저장소에서 원본 판을 설치하는 방법이다.

```bash
claude plugin marketplace add parkjui92/AI-Assembly
claude plugin install bill-review@ai-assembly
```

- 설치 뒤 Claude 앱을 다시 시작하고, 같은 작업 폴더에서 "법률안 검토보고서 작성팀의 팀원과 스킬을 표로 보여줘"로 확인
- 법령 현행 확인에는 [korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp), 한글 문서 읽기·변환에는 [kordoc](https://github.com/chrisryugj/kordoc) 연결 권장
- 인증키(국가법령정보 OC 등)는 채팅창이 아니라 작업 폴더의 `.env`에 보관

## 유의

- 초안은 에이전트가, 쟁점 판단과 결론은 작성자가 함
- 비공개 자료·내부 회답·개인정보는 반입 기준을 확인한 뒤 넣음
- 강의자료(원본 저장소의 `slides/`, 이 사본에는 없음) 출처는 각 슬라이드 아래 줄에 표기

문의: 박주이 · 한양대학교 과학기술정책연구소 · parkjui92@gmail.com
라이선스: 플러그인 MIT(`plugins/bill-review/LICENSE`)
