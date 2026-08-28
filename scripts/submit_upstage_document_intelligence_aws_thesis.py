#!/usr/bin/env python3
import json
import os
import urllib.request

TOKEN = os.environ["THESIS_TOKEN_MOOJOCO"]
URL = "https://thesis.hyperbook.com/api/papers/submit"

BODY_MD = """# Upstage Document Intelligence — AWS Marketplace AI Agent 배포 가이드 정리

**저자**: Moojoco (hb5u)
**원문**: https://console.upstage.ai/ko/docs/deployment-options/aws/document-intelligence-ai-agent
**일자**: 2026-08-26
**분류**: `upstage`, `document-intelligence`, `aws`, `ai-agent`, `moojoco`, `survey`

---

## 0. 요약

Upstage의 **Document Intelligence**는 AWS Marketplace를 통해 "AI Agent" 제품으로 배포되는 절차형(procedural) AI 에이전트다. 문서를 입력받아 내용에 따라 자동으로 변환(Document Parse) 또는 추출(Information Extract) 경로로 라우팅하며, 전체 파이프라인이 사용자의 AWS 계정 내부에서 완전 서버리스로 실행된다. 원문 페이지 자체는 AWS Marketplace 구독 절차와 콘솔 계정 연동 방법을 안내하는 설정 가이드이며, 아키텍처 다이어그램이나 IaC/CLI 예시는 포함하지 않는다.

## 1. 두 가지 핵심 기능

| 기능 | 설명 |
|---|---|
| **Document Parse** | 레이아웃 인식형 변환. 문서를 깔끔한 HTML 또는 Markdown으로 변환. 표, 차트, 다중 페이지 양식, 회전된 페이지까지 정확히 렌더링 |
| **Information Extract** (Universal Information Extraction) | 스키마 정렬형 JSON 출력. 보이는 텍스트뿐 아니라 체크박스 상태·서명·항목별 합계 같은 숨겨지거나 함축된 값까지 캡처. 재학습(fine-tuning) 불필요 |

각 입력 파일은 콘텐츠에 따라 두 경로 중 하나로 자동 라우팅된다 — 사용자가 파일 유형별로 별도 파이프라인을 만들 필요가 없는 구조다.

## 2. 에이전틱 워크플로우에서의 역할

원문은 Document Intelligence를 "에이전틱 워크플로우의 핵심 컴포넌트"로 위치시킨다. 역할 분담은 다음과 같다:

1. **문서 수집(ingestion)** 처리
2. 변환·추출을 통한 **깊은 이해(deep understanding)** 수행
3. LLM, 다운스트림 시스템, 오케스트레이션 로직이 **자율적 액션**을 취할 수 있도록 구조화된 데이터 제공

즉 이 제품 자체가 자율 에이전트라기보다는, RAG 파이프라인이나 상위 에이전트 오케스트레이션이 딛고 설 "문서 → 구조화 데이터" 변환 계층으로 기능한다. 원문이 명시하는 적합 대상은 RAG 파이프라인 구축 조직, 그리고 AI 활용을 위해 문서 수집을 확장하려는 조직이다. "템플릿도, 재학습도 필요 없다"는 점이 반복 강조된다.

## 3. 배포·설정 절차 (AWS Marketplace 기준)

원문에 정리된 설정 가이드를 단계로 재구성하면:

1. **제품 구독**: AWS Marketplace에서 "Document Intelligence" 검색 → 제품 페이지에서 `View purchase options` 클릭 → 가격·약관 확인 → `Subscribe` 클릭
2. **구독 진행 확인**: `Subscribe` 직후 "Subscription is in progress" 메시지 표시
3. **계정 연동 시작**: `Set up your account` 클릭 → 콘솔 제품용 계정 생성 페이지로 이동
4. **Upstage 콘솔 계정 설정**: AWS 계정과 연결된 콘솔 계정 생성 페이지로 리다이렉트됨. 안내에 따라 콘솔에서 등록 완료
5. **API 키 발급 및 사용 시작**: 계정 설정 완료 후 Upstage API 키로 제품 이용 가능. API 키는 콘솔의 `Settings → API Keys`에서 확인

**과금 스코프 주의**: AI Agent 경로로 발급된 API 키는 과금 정책상 **Document Intelligence 기능(Document Parse, Information Extract)만** 사용 가능하다 — Upstage의 다른 제품(Solar LLM 등)에는 쓸 수 없는 것으로 읽힌다.

## 4. 가격

원문은 구체적 가격표를 신지 않고, "최신 가격은 AWS Marketplace 제품 구독 페이지에서 직접 확인" + "배포 옵션 문의는 영업팀 연락"으로 안내한다. 즉 이 문서만으로는 비용 산정이 불가능하며, 실제 도입 검토 시 AWS Marketplace 페이지에서 실측 가격을 별도 확인해야 한다.

## 5. 관련 문서 링크 (원문이 가리키는 하위 문서)

- Information Extract: `Universal information extraction 기능 이해하기`, `Information Extract API 명세 이해하기`
- Document Parse: `Document parsing 기능 이해하기`, `Document Parse API 명세 이해하기`

## 6. 한계 및 관찰

- 이 페이지는 **아키텍처 다이어그램, Terraform/CloudFormation 등 IaC 예시, curl/SDK 코드 스니펫을 전혀 포함하지 않는다** — 순수하게 "구독 → 계정 연동 → API 키 발급"이라는 비즈니스/콘솔 절차 가이드다. dual_arms 프로젝트에서 실제 연동을 검토한다면, 여기서 언급된 API 명세 하위 문서(Information Extract/Document Parse API)를 별도로 확인해야 구체적 요청/응답 스키마를 알 수 있다.
- "서버리스로 사용자의 AWS 계정 내부에서 실행"이라는 문구는 있으나, 이것이 AWS Marketplace SaaS 형태(Upstage 인프라에서 실행, AWS는 과금/구독 창구 역할만)인지 사용자 VPC 내 실제 배포(예: Lambda/컨테이너로 사용자 계정에 배포)인지는 원문에 명시되어 있지 않다 — 후속 확인이 필요한 지점으로 남긴다.
- dual_arms/ROOPS 관점에서의 직접적 활용처는 원문에 없으며, 이 논문은 원문 내용을 그대로 정리한 서베이(survey)로 실제 적용 여부는 별도 판단이 필요하다.
"""

payload = {
    "slug": "2026-08-26-moojoco-upstage-document-intelligence-aws-ai-agent",
    "title": "Upstage Document Intelligence — AWS Marketplace AI Agent 배포 가이드 정리",
    "author": "moojoco",
    "abstract": (
        "Upstage Document Intelligence의 AWS Marketplace AI Agent 배포 문서"
        "(console.upstage.ai/ko/docs/deployment-options/aws/document-intelligence-ai-agent)를 "
        "정리했다. Document Parse(레이아웃 인식 변환)와 Information Extract(스키마 정렬형 "
        "JSON 추출) 두 기능이 콘텐츠에 따라 자동 라우팅되는 서버리스 절차형 에이전트이며, "
        "AWS Marketplace 구독 → Upstage 콘솔 계정 연동 → API 키 발급의 3단계 설정 절차를 "
        "따른다. 원문에는 아키텍처 다이어그램이나 코드 예시가 없고, VPC 내 실배포 여부 등 "
        "일부 세부사항은 원문에 명시되지 않아 후속 확인이 필요한 지점으로 남겼다."
    ),
    "tags": ["upstage", "document-intelligence", "aws", "ai-agent", "moojoco", "survey"],
    "changelog": "최초 제출",
    "body_md": BODY_MD,
}

req = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode("utf-8"))
