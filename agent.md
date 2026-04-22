# 서울/인천 디스플레이 카드 개편 작업 지시서

## 1. 작업 목적
`code/2025122903_pico.py` 와 `code/2025123003_nodered.json` 을 수정하여, Node-RED 대시보드에서 `SEOUL` 탭과 `INCHEON` 탭에 기기별 `디스플레이 카드` 만 표시되도록 개편한다.

이번 작업의 핵심은 다음과 같다.

1. 서울/인천 탭에는 디바이스별 `디스플레이 카드` 만 나타나게 한다.
2. 기존에 검토했던 `설정` 탭, `제어 설정 카드`, `네트워크 설정 카드` 관련 목표는 이번 작업 범위에서 제거한다.
3. Pico 가 보내는 실제 상태 데이터를 디스플레이 카드 레이아웃에 맞게 표시한다.
4. HOME / SEARCH / LEVEL / 로그인 / SMS / 기존 차트/알림 흐름은 깨지지 않게 유지한다.

추가 원칙:

- 최신 수정사항에 직접 언급되지 않은 나머지 항목은 이전에 확정한 방향을 그대로 유지한다.

## 2. 절대 수정하지 말아야 할 범위
- 로그인 기능
- SMS 문자메시지 기능
- SEARCH 기능
- LEVEL 기능
- HOME 탭 동작
- 서울/인천 탭 바깥의 권한 처리 및 탭 제어 로직

주의: 이번 작업에서 화면에 설정 UI 를 남기면 실패다. 사용자에게 보이는 화면은 `디스플레이 카드` 만 있어야 한다.

## 3. 현재 코드 분석 요약

### 3.1 Pico 현재 상태
파일: `code/2025122903_pico.py`

현재 Pico 코드는 대략 아래 구조다.

- MQTT topic 기본 prefix: `{uid}/pico/{region}/{device}/`
- 현재 발행 데이터:
  - `water_level`
  - `battery`
  - `solar_control`
  - `network_control`
  - `control_status`
- 현재 구독 데이터:
  - `control_cmd`
- 현재 payload는 `{ region, device_id, type, timestamp, value }` 형태 중심이다.

즉, 지금 Pico 코드는 새 디스플레이 카드에서 요구하는 `lte`, `pressure_enabled`, `version_text`, `current_a`, `flow_ton`, `motor_date` 같은 화면 전용 상태를 아직 충분히 정리하지 않았다.

### 3.2 Node-RED 현재 상태
파일: `code/2025123003_nodered.json`

현재 대시보드에는 아래 탭이 있다.

- `HOME`
- `SEARCH`
- `LEVEL`
- `SEOUL`
- `INCHEON`

현재 서울/인천 탭에는 기존 `Bundle Premium` 템플릿과 `FIX` 제어 템플릿이 섞여 있다. 이번 작업에서는 사용자 화면 기준으로 `FIX` 성격의 설정/제어 UI 를 제거하고, 기기별 디스플레이 카드만 남기도록 정리해야 한다.

## 4. 요구사항 재해석

### 4.1 탭 역할
- 대시보드에는 `HOME`, `SEARCH`, `LEVEL`, `SEOUL`, `INCHEON` 탭만 둔다.
- `설정` 탭은 만들지 않는다.
- `제어 설정 카드`, `네트워크 설정 카드` 는 이번 작업 범위에서 제거한다.
- Node-RED 화면에는 기기별 `디스플레이 카드` 만 나타낸다.
- 서울/인천 탭의 카드는 지역과 기기 수만큼 동적으로 증감한다.

### 4.2 디스플레이 카드에 들어가야 하는 항목
- `ch`: 0~15
- `lte`: on/off
  - on 이면 상단에 `LTE` 문구와 우측 상단 무선 아이콘을 표시
  - off 이면 `LTE` 문구와 우측 상단 무선 아이콘을 모두 표시하지 않음
- `송신`: on/off
- `수신`: on/off
- `버전 표기`: 수신 데이터 예시 `V5.2`
- `수위`: 0~100%
- `관정`: m
- `압력 모드`: on/off
  - on 이면 중앙 제목 문구를 `압력` 으로 표시
  - off 이면 중앙 제목 문구를 `오뚜기` 로 표시
- `정지`: %
- `가동`: %
- `알람`: %
- `펌프`: on/off
- `전류`: A
- `유량`: Ton
- `모터설치 날짜`
  - 날짜만 표시, 시간은 표시하지 않음
- `solar`: on/off
- `bat`: 1~3 단계
- `현재 날짜 필드`

### 4.3 UI 제약
- 서울/인천 탭에서는 기기별로 `디스플레이 카드` 만 렌더한다.
- `제어 설정 카드`, `네트워크 설정 카드`, 관련 입력 폼은 사용자 화면에 나타나면 안 된다.
- 전체적인 카드 배치는 첨부된 디스플레이 카드 시안을 따른다.
- `디스플레이 카드` 의 폭은 기존 카드의 폭과 동일하게 맞춘다.
- 다만 디스플레이 카드 내부 `ui`, `배경색상`, `글자폰트`, `글자크기`, `도트모양`, `도트색상` 은 기존 Node-RED UI 코드를 참조하여 제작한다.
- 숫자, 날짜, 코드값은 모두 예시값이며 실제 데이터 바인딩으로 렌더한다.

### 4.4 시안 이미지 해석 기준
시각 레퍼런스는 아래 파일 하나만 사용한다.

- `image/00_main/01_display_card.png`

중요:

- 시안 안 숫자와 날짜는 모두 예시값이다.
- 상단 `LTE` 는 상태 항목이다.
- 상단 `V5.2` 는 고정 문구가 아니라 수신 데이터다.
- 카드 중앙 제목 문구는 고정이 아니라 `압력 모드` 상태에 따라 `압력` 또는 `오뚜기` 로 바뀐다.
- 하단 날짜 라벨은 기존 `모터시동` 이 아니라 `모터설치` 로 해석한다.
- `LTE off` 일 때는 상단 우측 무선 아이콘도 함께 숨긴다.
- `모터설치` 는 날짜만 표시한다.

## 5. 핵심 해석 및 설계 원칙

### 5.1 기기 식별
- 각 지역에는 여러 대의 Pico 보드가 존재한다.
- `region_code`, `device_code` 는 특정 기기의 데이터를 식별하기 위한 실제 키다.
- Node-RED 는 이 식별자 기준으로 수신한 데이터를 지역 탭의 해당 카드에 연결해야 한다.

### 5.2 배터리 단계 규칙
- 배터리는 3단계만 사용한다.
- 사용 이미지는 아래 3개다.
  - `image/00_main/25_battery.png`
  - `image/00_main/26_battery.png`
  - `image/00_main/27_battery.png`
- 권장 매핑:
  - 1단계 -> `25_battery.png`
  - 2단계 -> `26_battery.png`
  - 3단계 -> `27_battery.png`

### 5.3 송신/수신 상태 표시 주기
- 송신/수신 상태는 실시간 점멸형으로 처리하지 않는다.
- 1분마다 1회 상태 체크 후 그 결과를 화면에 반영한다.

### 5.4 LTE 표시 규칙
- `lte=on` 이면 상단 `LTE` 문구와 우측 상단 무선 아이콘을 표시한다.
- `lte=off` 이면 상단 `LTE` 문구와 우측 상단 무선 아이콘을 표시하지 않는다.
- LTE 표시는 고정 텍스트가 아니라 상태 기반 표시다.

### 5.5 `가동` 값의 의미
- `정지`, `가동`, `알람` 값은 단순 표시값이 아니라 현장 설비 운전 기준값으로 해석한다.
- 디스플레이 카드는 그 기준값을 표시하는 역할을 한다.

### 5.6 디스플레이 전용 원칙
- 이번 작업 범위에서 설정 UI 는 만들지 않는다.
- 기존 `FIX` 카드의 `PUMP/LIGHT/FAN/RESET` 4채널 제어 UI 도 화면에서 제거 대상이다.
- 네트워크 설정 UI 및 프로토콜 설계는 이번 문서의 타깃 범위에서 제외한다.

### 5.7 팬 터치 기반 펌프 제어 규칙
- 팬 이미지가 정지 상태일 때 팬 이미지를 터치하면 Node-RED 는 Pico 로 `펌프 ON` 데이터를 송신한다.
- Pico 가 `ON` 데이터를 수신했고 실제 상태가 `pump=on` 으로 반영되었다고 Node-RED 가 판단한 경우에만 팬 이미지를 회전 상태로 만든다.
- 팬 이미지가 회전 상태일 때 팬 이미지를 터치하면 Node-RED 는 Pico 로 `펌프 OFF` 데이터를 송신한다.
- Pico 가 `OFF` 데이터를 수신했고 실제 상태가 `pump=off` 로 반영되었다고 Node-RED 가 판단한 경우에만 팬 이미지를 정지 상태로 만든다.
- 즉 팬 애니메이션은 터치 직후 낙관적으로 바꾸지 않고, Pico 확인 후에만 바뀐다.

### 5.8 랜덤 테스트 데이터 운영 원칙
- Pico 에서는 Node-RED 와의 송수신 확인을 위해 각 데이터 항목에 대한 임의 랜덤 데이터를 생성할 수 있어야 한다.
- 랜덤 테스트 데이터도 실제 운용과 동일한 payload 키와 topic 구조를 사용해야 한다.
- 테스트가 끝나면 랜덤 데이터 생성 코드를 제거하거나 비활성화하고, 같은 payload 구조로 실기기 센서값을 넣어야 한다.
- 즉 `테스트 모드` 와 `실기기 모드` 는 데이터 값의 출처만 다르고, topic/payload 구조는 동일해야 한다.

## 6. 권장 식별자 / 토픽 / 페이로드 설계

### 6.1 식별자 구조
- `display_region`
  - 지역 탭 구분용. 현재는 `서울`, `인천`
- `region_code`
  - 실제 Pico 매칭용 4자리 영문
- `device_code`
  - 실제 Pico 매칭용 4자리 숫자

권장 원칙:

- Node-RED 는 `dashboard_state` 를 수신하면 `display_region` 기준으로 지역 탭을 결정한다.
- 같은 지역 안에서는 `region_code + device_code` 조합으로 카드별 데이터를 식별한다.
- 서울/인천 탭 카드 수는 고정값이 아니라 실제 지역별 기기 수만큼 동적으로 결정한다.
- 이번 작업에서는 설정/네트워크 UI용 명령 topic 은 설계하지 않지만, 팬 터치 기반 `펌프 ON/OFF` 제어용 topic 은 명확히 정의한다.

### 6.2 canonical topic
- Pico -> Node-RED 디스플레이 상태:
  - `{uid}/pico/{region_code}/{device_code}/dashboard_state`
- Node-RED -> Pico 펌프 제어 명령:
  - `{uid}/pico/{region_code}/{device_code}/pump_cmd`
- Pico -> Node-RED 펌프 제어 확인 상태:
  - `{uid}/pico/{region_code}/{device_code}/pump_state`

### 6.3 `dashboard_state` payload 권장안
```json
{
  "schema": "dashboard_state/v2",
  "timestamp": "2026-03-30T12:40:00+09:00",
  "region_code": "SEOU",
  "device_code": "0001",
  "display": {
    "region": "서울"
  },
  "data": {
    "channel": 15,
    "lte": "on",
    "tx": "on",
    "rx": "off",
    "version_text": "V5.2",
    "water_level_pct": 80,
    "well_depth_m": 60,
    "pressure_enabled": true,
    "stop_pct": 80,
    "run_pct": 30,
    "alarm_pct": 40,
    "pump": "on",
    "current_a": 12.5,
    "flow_ton": 24,
    "motor_install_date": "2026-02-30",
    "solar": "on",
    "battery_stage": 3,
    "current_date": "2026-03-30"
  }
}
```

설계 원칙:

- `pressure_enabled` 가 `true` 이면 카드 중앙 제목을 `압력` 으로 표시한다.
- `pressure_enabled` 가 `false` 이면 카드 중앙 제목을 `오뚜기` 로 표시한다.
- `dashboard_state` 는 Pico 가 실제 확인한 최신 상태여야 하며, Node-RED 가 임의 추정한 값이면 안 된다.
- `pump` 는 최종 확인된 실제 펌프 상태여야 한다.
- 랜덤 테스트 모드와 실기기 모드 모두 같은 payload 키를 사용한다.

### 6.4 `pump_cmd` payload 권장안
```json
{
  "schema": "pump_cmd/v1",
  "timestamp": "2026-03-30T12:41:00+09:00",
  "region_code": "SEOU",
  "device_code": "0001",
  "command": "on"
}
```

또는

```json
{
  "schema": "pump_cmd/v1",
  "timestamp": "2026-03-30T12:41:05+09:00",
  "region_code": "SEOU",
  "device_code": "0001",
  "command": "off"
}
```

### 6.5 `pump_state` payload 권장안
```json
{
  "schema": "pump_state/v1",
  "timestamp": "2026-03-30T12:41:01+09:00",
  "region_code": "SEOU",
  "device_code": "0001",
  "pump": "on",
  "result": "applied"
}
```

또는

```json
{
  "schema": "pump_state/v1",
  "timestamp": "2026-03-30T12:41:06+09:00",
  "region_code": "SEOU",
  "device_code": "0001",
  "pump": "off",
  "result": "applied"
}
```

설계 원칙:

- Node-RED 는 `pump_cmd` 전송 직후 팬 이미지를 회전/정지시키지 않는다.
- 반드시 `pump_state` 또는 이후 `dashboard_state.data.pump` 값으로 실제 적용을 확인한 뒤 UI를 바꾼다.
- `pump_state.result` 가 `applied` 가 아니면 팬 상태를 바꾸지 않는다.

### 6.6 테스트 모드 규칙
- Pico 코드에 `테스트 모드` 플래그를 둔다. 예: `USE_RANDOM_TEST_DATA = True`
- 테스트 모드에서는 각 필드를 랜덤 값으로 채워 `dashboard_state` 를 발행한다.
- 실기기 모드에서는 동일한 payload 구조에 실제 센서/제어 상태 값을 넣어 발행한다.
- 테스트 모드 종료 시 랜덤 생성 코드를 제거하거나 `USE_RANDOM_TEST_DATA = False` 로 전환한다.
- topic 과 payload key 는 테스트/실기기 전환과 무관하게 동일하게 유지한다.

### 6.7 기존 기능 호환 처리
- 기존 검색/차트/알림 로직이 필요한 경우, Node-RED 내부 normalizer 에서 `dashboard_state` 를 기존 downstream 형식으로 변환한다.
- 하지만 사용자 화면에는 디스플레이 카드만 남기고, 설정/제어 카드 UI 는 연결하지 않는다.

## 7. Node-RED에서 해야 할 일

### 7.1 수정 대상 범위
- 서울/인천 탭의 기기별 디스플레이 카드 UI
- 디스플레이 카드 렌더를 위한 수신/정규화 함수
- 기존 `FIX` 카드 및 설정 카드 관련 사용자 노출 UI 제거

### 7.2 UI 구현 원칙
- `image/00_main/01_display_card.png` 레이아웃을 기준으로 디스플레이 카드를 구성한다.
- 전체 배치는 시안 이미지를 따르되, 카드 내부 `ui`, `배경색상`, `글자폰트`, `글자크기`, `도트모양`, `도트색상` 은 기존 Node-RED UI 코드를 참조하여 제작한다.
- `디스플레이 카드` 의 폭은 기존 Node-RED 카드 폭과 동일하게 유지한다.
- 카드에는 아래 요소만 보여준다.
  - CH
  - LTE
  - 송신/수신 dot
  - 버전 텍스트
  - 수위
  - 관정
  - 중앙 제목 `압력/오뚜기`
  - 정지/가동/알람
  - 펌프 아이콘
  - 전류/유량
  - 모터설치 날짜
  - SOL
  - BAT
  - 현재 날짜
- `pressure_enabled` 값에 따라 `압력/오뚜기` 문구를 바꾼다.
- `lte=on` 일 때만 상단 `LTE` 문구와 우측 상단 무선 아이콘을 표시한다.
- `lte=off` 일 때는 `LTE` 문구와 우측 상단 무선 아이콘을 함께 숨긴다.
- 팬 이미지가 정지 상태일 때 터치하면 `pump_cmd(command:on)` 를 보낸다.
- 팬 이미지가 회전 상태일 때 터치하면 `pump_cmd(command:off)` 를 보낸다.
- 팬 애니메이션은 `pump_state` 또는 `dashboard_state.data.pump` 로 실제 적용이 확인된 뒤에만 바꾼다.
- 카드 내부 숫자와 날짜는 하드코딩하지 말고 모두 데이터 바인딩으로 처리한다.
- `모터설치 날짜` 는 날짜만 표시하고 시간은 표시하지 않는다.

### 7.3 Node-RED 함수 레벨 작업
- `dashboard_state` 수신 처리
- `pump_cmd` 발행 처리
- `pump_state` 수신 처리
- `region_code`, `device_code` 기반 카드 식별
- `display_region` 기반 지역 탭 라우팅
- 디바이스별 최신 display state 캐시 유지
- 디바이스별 최신 pump 확인 상태 캐시 유지
- 1분 주기 송신/수신 상태 표시 규칙 반영
- `pressure_enabled` 를 UI 문구 `압력/오뚜기` 로 변환
- 팬 터치 이벤트를 Pico 제어 명령으로 변환
- Pico 확인 전에는 팬 회전 상태를 바꾸지 않음
- 기존 `Bundle Premium` / `FIX` 기반 UI 중 화면에 필요 없는 부분 제거

권장 캐시 키 예시:

- `dashboard_state_{region_code}_{device_code}`
- `pump_state_{region_code}_{device_code}`

### 7.4 기존 기능 보호 원칙
- HOME, SEARCH, LEVEL, 로그인, SMS, 기존 차트/알림 흐름은 깨지지 않게 유지한다.
- 설정/제어 카드 UI 만 제거하고, 영향 없는 기존 흐름은 건드리지 않는다.

## 8. Pico에서 해야 할 일

### 8.1 기본 구조 변경
- Pico 는 디스플레이 카드에 필요한 최신 상태를 `dashboard_state` 로 발행한다.
- 이번 작업에서는 화면용 설정 카드/네트워크 카드용 명령 프로토콜을 추가하지 않는다.
- 팬 터치 제어를 위해 `pump_cmd` 를 수신하고, 반영 결과를 `pump_state` 로 응답한다.
- `tx`, `rx` 는 1분 주기 상태 체크 결과로 계산한다.
- `pressure_enabled` 값을 함께 보내서 Node-RED 가 `압력/오뚜기` 문구를 바꿀 수 있게 한다.
- 테스트 단계에서는 랜덤 데이터 생성 모드를 두고, 실기기 연결 단계에서는 동일 payload 구조로 실제 값을 발행한다.

### 8.2 Pico 내부 권장 상태 구조
```python
dashboard_state = {
    "display_region": "서울",
    "region_code": "SEOU",
    "device_code": "0001",
    "channel": 15,
    "lte": "on",
    "tx": "on",
    "rx": "off",
    "version_text": "V5.2",
    "water_level_pct": 80,
    "well_depth_m": 60,
    "pressure_enabled": True,
    "stop_pct": 80,
    "run_pct": 30,
    "alarm_pct": 40,
    "pump": "on",
    "current_a": 12.5,
    "flow_ton": 24,
    "motor_install_date": "2026-02-30",
    "solar": "on",
    "battery_stage": 3,
    "current_date": "2026-03-30"
}
```

### 8.3 통신 상태 값 정의
- `tx`: 1분마다 1회 송신 상태 체크 결과
- `rx`: 1분마다 1회 수신 상태 체크 결과
- `lte`: on/off 상태값
- `pump`: 실제 반영된 on/off 상태값

## 9. 구체적인 구현 순서

1. 현재 flow JSON 과 pico.py 를 백업한다.
2. 서울/인천 탭에서 사용자에게 보이는 설정/제어 UI를 제거할 범위를 식별한다.
3. `dashboard_state` 기준으로 디스플레이 카드만 렌더하는 구조를 설계한다.
4. `pressure_enabled -> 압력/오뚜기` 문구 전환 로직을 UI에 반영한다.
5. `lte`, `tx`, `rx`, `battery_stage` 표시 규칙을 UI에 반영한다.
6. 팬 이미지 터치 -> `pump_cmd` 발행 -> `pump_state` 확인 후 팬 애니메이션 변경 흐름을 구현한다.
7. Pico 에서 랜덤 테스트 데이터 기반 `dashboard_state` 발행 구조를 먼저 정리한다.
8. Node-RED 와 Pico 간 랜덤 데이터 송수신 및 펌프 ON/OFF 테스트를 수행한다.
9. 테스트 완료 후 랜덤 데이터 모드를 제거하거나 비활성화하고, 같은 payload 구조로 실기기 센서값을 연결한다.
10. 기존 기능 회귀 테스트를 수행한다.

## 10. 검증 체크리스트

### 10.1 UI
- 스마트폰 세로 화면에서 서울/인천 탭에는 지역과 기기 수만큼 디스플레이 카드가 동적으로 보인다.
- `설정` 탭이 보이지 않는다.
- `제어 설정 카드`, `네트워크 설정 카드` 가 어디에도 렌더되지 않는다.
- 첨부된 디스플레이 카드 시안과 같은 레이아웃과 톤을 유지한다.
- `디스플레이 카드` 의 폭이 기존 카드 폭과 동일하다.
- 카드 내부 `배경색상`, `폰트`, `글자크기`, `도트모양`, `도트색상` 이 기존 UI 스타일과 일관된다.
- 카드 중앙 제목이 상태에 따라 `압력` 또는 `오뚜기` 로 바뀐다.
- LTE 상태가 on/off 에 따라 상단 `LTE` 문구와 우측 상단 무선 아이콘 표시/비표시로 올바르게 동작한다.
- 상단 버전 텍스트가 고정값이 아니라 실제 수신 데이터로 표시된다.
- 송신/수신 상태는 1분 주기 체크 결과로 표시된다.
- 배터리는 3단계만 표시된다.
- `모터설치` 라벨과 날짜가 올바르게 표시되며, 시간은 표시되지 않는다.
- 팬 정지 상태에서 팬 이미지를 터치하면 Pico 확인 후 회전 상태로 바뀐다.
- 팬 회전 상태에서 팬 이미지를 터치하면 Pico 확인 후 정지 상태로 바뀐다.

### 10.2 데이터
- `dashboard_state` 수신 시 각 카드의 값이 실제 데이터로 갱신된다.
- `pump_cmd` 와 `pump_state` 가 명확한 topic/payload 구조로 송수신된다.
- `region_code`, `device_code` 가 카드 식별에 사용된다.
- 숫자와 날짜는 예시값이 아니라 실제 수신값으로 표시된다.
- 랜덤 테스트 모드에서도 실기기 모드와 동일한 payload 키를 사용한다.
- 테스트 종료 후 랜덤 데이터 제거/비활성화 후에도 같은 topic 구조로 실기기 데이터가 표시된다.

### 10.3 회귀 테스트
- HOME 탭 진입 가능
- SEARCH 기능 정상
- LEVEL 기능 정상
- 로그인/로그아웃 정상
- SMS 관련 흐름 오류 없음
- 기존 차트/알림 흐름 정상

## 11. 구현 시 주의사항
- 현재 Dashboard는 Angular 기반 `ui_template` 스타일이다. 다른 프론트엔드 체계로 갈아타지 말 것.
- 설정 탭/설정 카드 관련 요구는 이번 작업 범위에서 제거되었음을 문서와 구현 모두에 일관되게 반영할 것.
- UI에는 낙관적 설정 상태를 만들지 말고, Pico 가 보낸 실제 display state 만 표시할 것.

## 12. 최종 산출물
- 수정된 `code/2025122903_pico.py`
- 수정된 `code/2025123003_nodered.json`
- 서울/인천 탭에서 동작하는 기기별 `디스플레이 카드` UI
- 팬 터치 기반 `pump_cmd` / `pump_state` 제어 흐름
- 테스트 모드와 실기기 모드에 공통으로 사용하는 명확한 topic/payload 구조
- 디스플레이 전용 `dashboard_state` 프로토콜 정리
- 기존 기능 비파괴 검증 결과

## 13. 확인이 필요한 사항
현재 없음.

## 14. 2026-03-30 실제 반영 현황

### 14.1 수정 및 반영 완료 파일
- 수정 완료: `code/2025122903_pico.py`
- 수정 완료: `code/2025123003_nodered.json`
- 문서 반영: `agent.md`

추가 백업/기록 파일:

- `code/2025122903_pico.py.bak-20260330`
- `code/2025123003_nodered.json.bak-20260330`
- `live_flows_backup_20260330.json`
- `live_flows_deploy_20260330.json`
- `live_flows_backup_20260330_displayfix.json`
- `live_flows_backup_20260330_displayheight.json`
- `pico_device_main_backup_20260330.py`

### 14.2 현재 live 동작 상태
- Node-RED 는 `http://localhost:1880` 에서 실행 중이다.
- Dashboard 는 `http://localhost:1880/ui/` 에서 실행 중이다.
- Dashboard 로그인 계정은 `admin / 0000` 기준으로 확인했다.
- Pico 는 USB 로 PC 에 연결한 상태에서 수정본을 반영했고, Node-RED 와 실제 MQTT 송수신을 확인했다.
- 현재 서울 탭에서 디스플레이 카드가 실제로 렌더링되는 것을 브라우저로 확인했다.

### 14.3 현재 MQTT 송수신 구조
- 현재 Pico 발행 기준 canonical topic:
  - `1/pico/SEOU/0002/dashboard_state`
  - `1/pico/SEOU/0002/pump_state`
- 현재 Pico 구독 기준 canonical topic:
  - `1/pico/SEOU/0002/pump_cmd`
- Node-RED 는 `All Devices` MQTT 입력 노드에서 `+/pico/+/+/+` 를 구독한다.
- 디스플레이 카드는 `dashboard_state` 를 기준으로 렌더링한다.
- 팬 터치 시 Node-RED 가 `pump_cmd` 를 발행하고, Pico 의 `pump_state` 또는 이후 `dashboard_state.data.pump` 로 실제 반영 여부를 확인한 뒤 팬 회전 상태를 바꾼다.

### 14.4 현재 Pico 설정값
- `MQTT_BROKER = "192.168.1.110"`
- `MQTT_PORT = 1883`
- `MQTT_USER_ID = "1"`
- `DISPLAY_REGION = "서울"`
- `REGION_CODE = "SEOU"`
- `DEVICE_CODE = "0002"`
- `USE_RANDOM_TEST_DATA = True`

정리:

- 현재는 테스트 검증 단계이므로 Pico 가 랜덤 데이터 기반 `dashboard_state` 를 발행한다.
- 단, 테스트 모드여도 실기기 모드와 동일한 topic/payload 구조를 사용하도록 맞춰 두었다.
- 실기기 전환 시에는 `USE_RANDOM_TEST_DATA = False` 로 바꾸고, 동일 payload 구조에 실제 센서/설비 값을 연결하면 된다.

### 14.5 현재 디스플레이 카드 구현 상태
- `설정` 탭은 제거된 상태로 유지한다.
- `제어 설정 카드`, `네트워크 설정 카드` 는 렌더링하지 않는다.
- 서울/인천 탭에는 디바이스별 `디스플레이 카드` 만 표시한다.
- `pressure_enabled = true` 이면 카드 중앙 제목은 `압력` 으로 표시한다.
- `pressure_enabled = false` 이면 카드 중앙 제목은 `오뚜기` 로 표시한다.
- `lte = on` 이면 상단 `LTE` 문구와 우측 무선 아이콘을 표시한다.
- `lte = off` 이면 상단 `LTE` 문구와 우측 무선 아이콘을 모두 숨긴다.
- `version_text` 는 고정 문구가 아니라 수신 데이터로 표시한다.
- `모터시동` 표기는 `모터설치` 로 변경 완료했다.
- `모터설치 날짜` 는 날짜만 표시하고 시간은 표시하지 않는다.
- 배터리는 3단계 표시로 구현했다.

### 14.6 로그인 ID 와 MQTT 사용자 ID 처리 원칙
- Dashboard 로그인 ID `admin` 은 MQTT 사용자 ID 와 별개다.
- 현재 Pico 의 MQTT 사용자 ID 는 `1` 이다.
- 따라서 디스플레이 카드 렌더러는 `현재 로그인 ID == MQTT UID` 를 강제하지 않고, 수신된 카드 상태를 지역 기준 저장소에 캐시한 뒤 서울/인천 탭에 표시하도록 수정했다.
- 팬 터치로 `pump_cmd` 를 보낼 때는 카드에 저장된 실제 `uid` 값을 사용해 올바른 Pico topic 으로 발행한다.

### 14.7 한글/지역명 처리 보완
- 일부 환경에서 Pico payload 의 `display.region` 한글 문자열이 깨질 수 있는 현상을 확인했다.
- 현재 Node-RED 는 `display.region` 값이 정상일 때는 그 값을 사용하고, 깨져 있거나 비정상일 때는 `region_code` 기준 매핑(`SEOU -> 서울`, `INCH -> 인천`)으로 안전하게 라우팅하도록 보완했다.
- 따라서 한글 payload 문자열이 깨져도 서울/인천 카드 라우팅은 유지된다.

### 14.8 카드 높이 및 스크롤 보완
- 우측 스크롤바로 카드 내부를 올리고 내리지 않아도 카드 전체가 보이도록 수정했다.
- 현재 디스플레이 카드 템플릿은 부모 `md-card`, `nr-dashboard-cardcontainer`, `nr-dashboard-cardpanel` 높이를 카드 실제 높이에 맞춰 자동 확장한다.
- 기본 카드 보드 높이 기준은 `.dc-region-board { min-height: 330px; }` 이다.
- 카드 내부 3열(`수위/압력-오뚜기/펌프`) 기본 높이 기준은 `.dc-water, .dc-mode, .dc-pump { min-height: 178px; }` 이다.

높이 추가 조정 기준:

- 카드 전체 높이를 더 키우고 싶으면 `.dc-region-board` 의 `min-height` 값을 올린다.
- 카드 내부를 더 압축하고 싶으면 `.dc-water, .dc-mode, .dc-pump` 의 `min-height` 값을 줄인다.
- 단순히 Node-RED 위젯 `height` 만 고정 증가시키는 방식보다, 현재처럼 부모 높이 자동 확장 방식이 동적 카드 수 대응에 더 안전하다.

### 14.9 Node-RED live 검증 결과
- `All Devices` 노드가 MQTT topic `+/pico/+/+/+` 를 수신하는 것을 확인했다.
- `dashboard_state` 수신 시 서울 탭에 디스플레이 카드가 실제로 렌더링되는 것을 브라우저에서 확인했다.
- `pump_cmd on/off` 발행 후 `pump_state(result=applied)` 와 `dashboard_state.data.pump` 반영을 확인했다.
- 서울 탭 카드가 스크롤바 없이 전체 표시되는 것을 확인했다.

### 14.10 운영상 주의사항
- `node-red` 를 추가로 한 번 더 실행하면 `Error: port in use` 가 발생할 수 있는데, 이는 기존 Node-RED 가 이미 `1880` 포트를 사용 중이라는 뜻이므로 정상이다.
- 실기기 전환 전까지는 테스트용 랜덤 데이터가 보이는 상태이므로, 현장 센서값과 동일하다고 가정하면 안 된다.
- 실기기 전환 시에는 `USE_RANDOM_TEST_DATA` 만 끄고, topic/payload 구조는 유지해야 한다.
## 15. 2026-03-30 추가 반영 현황

### 15.1 Pico 랜덤데이터 보완
- 테스트 모드에서 `lte`, `tx`, `rx` 값을 랜덤 생성하도록 보완했다.
- `lte = off` 인 경우 `tx = off`, `rx = off` 가 함께 적용되도록 정리했다.
- 따라서 테스트 모드에서도 `LTE 문구`, `우측 무선 아이콘`, `송신/수신 도트`가 실제 수신 데이터처럼 표시/미표시된다.
- 송신 도트는 `on = 파랑`, `off = 회색`, 수신 도트는 `on = 빨강`, `off = 회색`으로 동작한다.
- USB 연결된 Pico 보드의 `main.py` 에도 같은 내용을 반영했다.

### 15.2 디스플레이카드 UI 보완
- 팬 아이콘은 기존 대비 `1.5배` 확대했다.
- `관정` 아래 프로그레스바는 제거했다.
- `SOL`, `BAT`, `현재날짜`는 한 줄에 유지되도록 간격과 글자 크기를 조정했다.
- `수위`, `펌프` 제목은 이전 조정본 대비 약 `20%` 줄였다.
- `정지`, `가동`, `알람`은 문구와 값이 같은 줄에 보이도록 정리했다.
- `수위값`은 추가 요청에 따라 다시 약 `10%` 줄였다.
- `수위`, `압력/오뚜기`, `펌프` 3영역 간격과 정렬을 시안에 가깝게 미세조정했다.
- `전류값/유량값`은 팬 아이콘 수직 중심선 기준으로 정렬했다.
- `관정` 문구는 `전류값` 첫 줄과 같은 높이에 오도록 조정했다.
- `수위` 영역의 왼쪽 여백과 `펌프` 영역의 오른쪽 여백을 대칭에 가깝게 맞췄다.

### 15.3 상단 헤더 정렬 보완
- 상단 `CH / LTE / 송신 / 수신 / V5.2 / 무선아이콘`은 고정 6칸 슬롯 구조로 재정렬했다.
- `LTE` 와 `무선아이콘`은 `on/off` 에 따라 숨김 처리되지만, 자리 자체는 유지되도록 구현했다.
- 따라서 `LTE off` 상태에서도 `송신`, `수신`, `V5.2` 위치가 좌우로 흔들리지 않는다.
- Playwright 기준으로 `LTE on` / `LTE off` 두 상태의 상단 요소 좌표가 동일하게 유지되는 것을 확인했다.

### 15.4 추가 검증 결과
- MQTT 실수신 검증:
  - `lte=off, tx=off, rx=off`
  - `lte=on, tx=on, rx=on`
  - 다시 `lte=off, tx=off, rx=off`
- `관정` 과 `전류/유량` 블록의 상단 기준선이 사실상 같은 위치로 맞는 것을 확인했다.
- 최신 화면 확인 캡처:
  - `.codex_tmp/playwright/ui-seoul-after-uiadjust4.png`
  - `.codex_tmp/playwright/ui-seoul-lte-on-20260330-uiadjust4.png`
  - `.codex_tmp/playwright/ui-seoul-on-uiadjust5.png`
  - `.codex_tmp/playwright/ui-seoul-off-uiadjust5.png`
  - `.codex_tmp/playwright/ui-seoul-uiadjust6-final.png`

### 15.5 추가 백업 파일
- `code/2025122903_pico.py.bak-20260330-uiadjust4`
- `code/2025123003_nodered.json.bak-20260330-uiadjust4`
- `code/2025123003_nodered.json.bak-20260330-uiadjust5`
- `code/2025123003_nodered.json.bak-20260330-uiadjust6`
- `pico_device_main_backup_20260330_uiadjust4.py`

## 16. 2026-03-31 LEVEL 탭 실시간 수위 그래프 반영

### 16.1 반영 목적
- LEVEL 탭에서 각 Pico 기기의 수위 데이터를 MQTT로 받아 실시간 그래프로 표시한다.
- 기존 legacy topic `water_level` 수신은 유지하고, 동시에 `dashboard_state.data.water_level_pct`도 그래프 입력으로 사용한다.
- 따라서 디스플레이 카드와 LEVEL 그래프가 같은 원본 수위 데이터를 기준으로 동작한다.

### 16.2 Node-RED 반영 내용
- `code/2025123003_nodered.json`에 `LEVEL chart input normalize` 함수 노드를 추가했다.
- 이 노드는 아래 규칙으로 LEVEL 그래프 입력을 정규화한다.
  - `type = water_level` 또는 `battery`면 기존 메시지를 그대로 통과
  - `type = dashboard_state`면 `payload.data.water_level_pct`를 읽어 `water_level` 형식 메시지로 변환
- 접근 제어 노드 이후 LEVEL 그래프 라우터로 바로 연결하던 구조를, `LEVEL chart input normalize -> LEVEL 그래프 라우터` 구조로 변경했다.
- `to ui_chart: Water Level (%)`, `to ui_chart: Battery (%)` 함수는 `region_code`를 지역명으로 매핑해 series 이름을 `서울-0002`, `인천-0002`처럼 표시하도록 보정했다.

### 16.3 동작 기준
- LEVEL 탭의 수위 그래프는 MQTT topic `+/pico/+/+/+`에서 들어오는 기기 데이터를 사용한다.
- 각 기기는 `지역-기기코드` 단위의 개별 series로 그래프에 누적된다.
- 따라서 서울 장비가 여러 대면 서울 장비 수만큼 선이 늘어나고, 인천 장비도 같은 방식으로 추가된다.

### 16.4 검증 결과
- `code/2025123003_nodered.json` JSON 파싱 정상 확인
- live Node-RED `/flows` 기준으로 `LEVEL chart input normalize` 노드 존재 확인
- live Node-RED `/flows` 기준으로 접근 제어 노드가 새 normalize 노드를 거치도록 배선 변경 확인
- live Node-RED에 full deploy 반영 완료

### 16.5 2026-03-31 추가 보정
- 실운영 확인 중 `current_user_id` 가 `null` 인 상태에서도 디스플레이 카드는 수신되지만, LEVEL 그래프는 접근 제어 경로에 묶여 있어 `No data` 로 남는 문제가 확인됐다.
- 따라서 LEVEL 그래프 입력만큼은 `토픽 분리 & 속성 설정 -> LEVEL chart input normalize` 경로를 직접 타도록 수정했다.
- 접근 제어 노드는 기존 `Device Registry`, `Capture last value+ts`, `데이터 경보 분류` 경로에만 유지한다.
- 최종 live 배선 기준:
  - `토픽 분리 & 속성 설정 -> 접근 제어`
  - `토픽 분리 & 속성 설정 -> LEVEL chart input normalize`
  - `접근 제어 -> Device Registry / Capture last value+ts / 데이터 경보 분류`
- 임시 검증 노드로 확인한 결과, `current_user_id = null` 상태에서도 `temp_level_last_chart_verify` 에 `서울-0002` 수위값이 실제 기록됐고 차트 입력까지 도달함을 확인했다.

## 17. 2026-03-31 디스플레이 카드 오프라인 제거 보정

### 17.1 문제
- Pico 보드 접속이 끊겨도 `display_cards_store` 에 마지막 카드 상태가 계속 남아 서울/인천 탭에서 카드가 사라지지 않는 문제가 확인됐다.

### 17.2 반영 내용
- `code/2025123003_nodered.json` 의 `Display Cards UI Bridge` 에 stale card prune 로직을 추가했다.
- 카드별 `updated_at` 기준으로 timeout 을 계산해 마지막 수신 이후 일정 시간이 지나면 `display_cards_store` 에서 해당 카드를 삭제한다.
- timeout 계산은 기존 alive 기준과 동일하게 `pico_publish_ms`, `alive_mult`, `alive_min_ms`, `alive_max_ms` 를 사용한다.
- 별도 inject 노드 `Display Cards Offline Tick` 를 추가해 5초마다 prune 을 수행하고, 서울/인천 탭에 최신 snapshot 을 다시 밀어준다.

### 17.3 검증 결과
- live Node-RED 반영 후 stale 상태였던 `서울 / 0002` 카드가 `display_cards_store` 에서 제거된 것을 확인했다.
- 같은 시점에 최근 데이터가 계속 들어오던 `인천 / 0001` 카드만 `display_cards_store` 에 남아 있는 것을 확인했다.
- 따라서 Pico 가 끊긴 카드만 자동 제거되고, 살아 있는 카드만 유지되는 동작으로 정리됐다.

## 18. 2026-03-31 UI 문구 및 카드 제목 보정

### 18.1 대시보드 UI 문구 `??` 보정
- 서울/인천 디스플레이 카드 안에서 한글 문구가 `??` 로 깨져 보이는 문제가 확인됐다.
- live Node-RED 기준으로 사용자에게 실제로 보이는 `ui_template`, `ui_group`, `ui_tab`, `ui_chart`, `ui_toast` 표시 문자열을 다시 동기화했다.
- 보정 후 디스플레이 카드에는 `송신`, `수신`, `수위`, `관정`, `압력`, `오뚜기`, `정지`, `가동`, `알람`, `모터설치` 가 정상 표시되도록 정리했다.
- LEVEL 탭의 그룹명도 `LEVEL 그래프` 로 복구했다.

### 18.2 경보 메시지 문구 보정
- 데이터 경보 분류 흐름에서 일부 경보 메시지 텍스트가 `??` 로 깨져 보이는 문제가 있었다.
- 아래 경보 메시지 문구를 live Node-RED에서 정상 한글 문구로 복구했다.
- `침수 위험 경고`
- `수위 정상 복귀`
- `배터리 경고`
- `배터리 긴급`
- 현재 경보 메시지 템플릿은 `[시간] [지역-기기]` 정보와 실제 수위/배터리 값을 포함해 정상 문자열로 발행되도록 정리됐다.

### 18.3 카드 상단 제목 구조 변경
- 기존 디스플레이 카드 묶음 상단에는 `서울 / 0001 외 1대` 같은 집계형 제목이 표시되고 있었다.
- 이 구조를 제거하고, 각 카드 바로 상단에 해당 카드의 `지역 / 기기코드` 가 개별 표시되도록 변경했다.
- 예:
  - `서울 / 0001`
  - `서울 / 0002`
- 이 보정은 `DISPLAY CARDS / SEOUL`, `DISPLAY CARDS / INCHEON` 두 템플릿에 모두 적용했다.
- 따라서 같은 지역 탭 안에서 기기 수가 증감해도, 반복 렌더링되는 각 카드마다 동일한 형식의 제목이 붙는다.
- 카드 내부 본문 UI, 팬 동작, 펌프 명령, 상단 `CH/LTE/송신/수신/V5.2`, 하단 `SOL/BAT/날짜` 구성은 변경하지 않았다.

### 18.4 실제 반영 및 검증 결과
- 저장 파일 기준 반영 대상: `code/2025123003_nodered.json`
- live Node-RED `/flows` 에서 아래 두 노드의 템플릿을 재배포했다.
- `DISPLAY CARDS / SEOUL`
- `DISPLAY CARDS / INCHEON`
- 배포 후 live flow 기준 확인 사항:
  - 기존 `getBoardTitle()` 집계 제목 제거
  - `dc-card-shell` 래퍼 추가
  - 각 카드 상단 `getCardTitle(card)` 렌더링 확인
- headless 브라우저 기준 서울 탭 실제 화면에서 카드별 제목 `서울 / 0001`, `서울 / 0002` 가 표시되는 것을 확인했다.

### 18.5 관련 백업 및 확인 파일
- live flow 백업:
  - `live_flows_backup_20260331_ui_text_sync_before.json`
  - `live_flows_backup_20260331_alert_textfix_before.json`
  - `live_flows_backup_20260331_percard_title_before.json`
- 확인 캡처:
  - `.codex_tmp/ui-seoul-percard-title.png`

## 19. 2026-04-01 현행 운영 기준

주의:

- 이 섹션은 현재 실제 반영 상태를 기준으로 작성한다.
- 아래 항목은 문서 상위의 초기 요구 중 `tx/rx`, SEARCH 노출, LOG 탭 부재, LEVEL 고정 그래프, 기기 타임스탬프 직접 신뢰와 관련된 오래된 내용을 대체한다.

### 19.1 현재 접속 및 실행 기준
- Mac 기준 Node-RED Dashboard 주소는 `http://127.0.0.1:1880/ui/` 이다.
- MQTT 브로커는 `192.168.1.197:1883` 기준으로 동작한다.
- Dashboard 로그인 계정은 `a / 1111` 기준이다.
- Pico Wi-Fi 설정은 `ssid = ije`, `password = dhkim316` 기준이다.

### 19.2 Pico 현재 반영 상태
- 현재 운영 파일은 `code/2025122903_pico.py` 이다.
- 실제 연결된 Pico 2대(`0001`, `0002`)에도 같은 기준으로 `main.py` 반영을 마쳤다.
- `dashboard_state` payload 에서는 더 이상 `tx`, `rx` 를 보내지 않는다.
- 현재 `dashboard_state.data` 에 포함되는 핵심 항목은 아래와 같다.
  - `channel`
  - `lte`
  - `version_text`
  - `water_level_pct`
  - `well_depth_m`
  - `pressure_enabled`
  - `stop_pct`
  - `run_pct`
  - `alarm_pct`
  - `pump`
  - `current_a`
  - `flow_ton`
  - `motor_install_date`
  - `solar`
  - `battery_stage`
  - `current_date`
- legacy topic 발행은 유지한다.
  - `water_level`
  - `battery`
  - `solar_control`
  - `network_control`

### 19.3 SEOUL / INCHEON 카드 현행 기준
- 서울/인천 탭에는 live 기기 기준 디스플레이 카드만 표시한다.
- 각 카드는 `지역 / 4자리 기기번호` 형식 제목으로 표시한다.
  - 예: `서울 / 0001`
  - 예: `서울 / 0002`
- 카드 상단에는 현재 `CH / LTE / 버전 / 무선아이콘`만 표시한다.
- 상단 `송신(도트)`, `수신(도트)` 는 제거했다.
- 카드 stale 판정은 Pico 가 보낸 `timestamp` 가 아니라 Node-RED 서버 수신 시각 기준으로 관리한다.
- 따라서 Pico 보드 시간이 틀려도 카드가 화면에서 깜빡이거나 바로 사라지지 않도록 보정했다.
- 팬 터치 기반 `pump_cmd -> pump_state / dashboard_state.data.pump 확인 후 반영` 규칙은 그대로 유지한다.

### 19.4 SEARCH / HOME 현행 기준
- SEARCH 탭은 삭제하지 않았고, 현재는 화면에서만 숨겨 둔 상태다.
- SEARCH 기능 자체는 보존되어 있어 필요 시 다시 노출 가능하다.
- `View All` 과 HOME `Online Devices` 는 실제 live 기기 수 기준으로 동작한다.
- `SEOU/0001` 과 `서울/01` 같이 서로 다른 topic 형식으로 들어와도 `서울-0001` 같은 canonical key 로 합산한다.

### 19.5 LOG 탭 현행 기준
- SEARCH 와 LEVEL 사이에 `LOG` 탭을 추가했다.
- LOG 탭에서는 접속된 기기를 드롭다운으로 선택해 시간대별 수신 기록을 본다.
- 같은 수신 주기 안에 들어온 값들은 한 줄 로그로 묶어서 보여준다.
- 데스크톱 기준 5열 그리드로 정렬해 표시한다.
- 화면에는 데이터 라벨과 값이 함께 보인다.
  - 예: `유량 20`
  - 예: `배터리 92`
- 아래 항목은 LOG 화면에 표시하지 않는다.
  - `송신`
  - `수신`
  - `버전`
  - `모터설치`
  - `네트워크`
  - `기준일`
- LOG 화면에서는 단위를 표시하지 않는다.
  - `%`
  - `m`
  - `A`
  - `Ton`
- empty 문구는 `수신된 데이터가 없습니다` 기준으로 맞췄다.

### 19.6 LEVEL 탭 현행 기준
- LEVEL 탭에는 기기 선택 드롭다운이 있다.
- 아무 기기도 선택하지 않으면 현재 접속된 모든 기기의 수위/배터리 그래프를 함께 표시한다.
- 특정 기기를 선택하면 해당 기기만 그래프에 표시한다.
- 그래프 series 이름은 `서울-0001`, `인천-0002` 형식의 canonical 이름만 사용한다.
- `서울-01`, `인천-01` 같은 중복 series 는 생성하지 않는다.
- LEVEL 그래프는 최근 60초 rolling window 기준으로 동작한다.
- Pico timestamp 가 현재 시각과 크게 어긋나면, LEVEL 차트는 서버 수신 시각으로 보정해서 그래프가 사라지지 않게 처리한다.

### 19.7 현재 확인된 운영 메모
- `0002` 보드는 간헐적으로 `2021-01-01` 같은 오래된 시간을 `dashboard_state.timestamp` 로 보내는 경우가 있다.
- 이 문제 때문에 서울 카드 깜빡임과 LEVEL 그래프 누락이 있었고, 현재 Node-RED 에서 서버 수신 시각 기준 보정으로 우선 막아 둔 상태다.
- 즉 카드/그래프 누락은 보정됐지만, 카드 하단 날짜 등 보드 자체 날짜 표시는 여전히 Pico 시간 동기화 상태의 영향을 받을 수 있다.
- 추후 완전 정리를 하려면 Pico 의 NTP/RTC 시간 동기화 보정이 추가로 필요하다.

## 20. 2026-04-01 실기기 MQTT 연동 및 최신 UI 보정

주의:

- 이 섹션은 `19.` 이후 추가 반영된 최신 상태를 기준으로 작성한다.
- 특히 `서울/인천` 중심 식별, LEVEL 탭의 배터리 그래프 표시, LEVEL/LOG 드롭다운 동작 관련 오래된 설명은 아래 기준으로 대체한다.

### 20.1 실기기 Pico MQTT 연동 기준
- 실기기 코드 베이스는 `gswater_python/gswater_python/app.py` 기준으로 정리했다.
- 실기기 MQTT 브리지를 위해 아래 파일을 추가/반영했다.
  - `gswater_python/gswater_python/mqtt_bridge_pico.py`
  - `gswater_python/gswater_python/main.py`
  - `gswater_python/gswater_python/umqtt/simple.py`
- 실기기 보드 `11101` 에는 `main.py`, `app.py`, MQTT 브리지, `umqtt` 패키지 업로드를 완료했다.
- 현재 실기기 MQTT 발행의 기준 토픽은 아래와 같다.
  - `1/pico/LS21/3456/dashboard_state`
  - `1/pico/서울/3456/water_level`
  - `1/pico/서울/3456/battery`
  - `1/pico/서울/3456/solar_control`
  - `1/pico/서울/3456/network_control`
- 즉 실제 시스템은 raw region code 토픽과 legacy 한글 토픽이 혼재할 수 있으며, Node-RED 에서 이를 같은 기기로 정규화해 처리한다.

### 20.2 실기기 DGUS / LTE 표시 기준
- 실기기 Pico 가 Wi-Fi 에 연결되면 DGUS 상단 `LTE_TXT (0x1010)` 에 `LTE` 문자열을 표시한다.
- Wi-Fi 접속이 끊기면 `LTE_TXT` 는 빈 문자열로 지운다.
- 이 동작은 `gswater_python/gswater_python/app.py` 에 반영되어 있으며, DGUS 텍스트 주소 기준은 아래와 같다.
  - `0,LTE_TXT,0x1010,LTE,3,Text`

### 20.3 디스플레이 카드 최신 표시 기준
- 카드 우측상단 제목은 더 이상 `서울/3456`, `인천/3456` 같은 표시명을 강제하지 않는다.
- 카드 제목은 Pico 가 보낸 raw `region_code / device_code` 를 그대로 사용한다.
  - 예: `LS21/3456`
- 카드 우측하단 날짜/시간 표시는 아래 형식으로 고정했다.
  - `2026-04-01  13:34:22`
- 서울 카드 우측상단 Wi-Fi 안테나 아이콘은 기존보다 약 1.3배 크게 조정했고, `V7.0PR` 텍스트와 같은 라인에 오도록 정렬 보정했다.

### 20.4 HOME / 탭 표시 최신 기준
- `Dynamic Devices` 탭은 삭제하지 않고 모바일/PC 모두에서 화면에 보이지 않도록 숨겼다.
- SEARCH 탭도 삭제하지 않았고, 현재는 화면에서만 숨겨 둔 상태다.
- HOME `Online Devices` 는 `display_cards_store` 와 canonical key 기준으로 계산한다.
- raw region code 토픽과 legacy 한글 토픽이 동시에 들어와도 같은 실제 기기 1대로 합산한다.

### 20.5 LOG 탭 최신 기준
- LOG 탭 드롭다운 기본 문구는 `모든 기기` 기준이다.
- LOG 탭 드롭다운은 현재 정상 동작하며, 선택한 기기코드가 입력창에 그대로 유지된다.
- LOG 탭 드롭다운은 주기적 재렌더링으로 깜빡이던 문제를 수정했다.
  - 옵션 목록/선택값이 실제로 바뀔 때만 갱신한다.
  - `track by dev.key` 를 사용해 불필요한 DOM 재생성을 막는다.
- LOG 탭에서는 `모든 기기` 상태도 정상 유지되며, 이 경우 전체 live 로그를 집계해서 보여준다.

### 20.6 LEVEL 탭 최신 기준
- LEVEL 탭은 현재 `수위 그래프`만 화면에 표시한다.
- 배터리 그래프는 화면에서 숨긴 상태다.
- LEVEL 드롭다운은 LOG 탭과 같은 스타일의 셀렉트 구조로 맞췄다.
- LEVEL 드롭다운의 `모든 기기`는 빈 값(`''`) 기반으로 처리한다.
- LEVEL 탭 드롭다운은 현재 아래 규칙으로 동작한다.
  - `모든 기기` 선택 시: 현재 live 기기 전체의 수위 그래프 표시
  - 특정 기기 선택 시: 해당 기기 수위 그래프만 표시
- LEVEL 탭 드롭다운에서 아래 문제를 추가 보정했다.
  - 선택 후 입력창이 다시 `모든 기기` 로 돌아가던 문제
  - 빈 문구의 옵션이 생기던 문제
  - 같은 실제 기기가 2개 또는 3개 옵션처럼 중복 보이던 문제
- 중복 원인은 같은 기기가 아래처럼 다른 토픽 키로 동시에 들어오는 구조였다.
  - `LS21-3456`
  - `서울-3456`
- 현재는 LEVEL 저장소에서 차트 히스토리 키를 canonical key 로 먼저 병합한 뒤 옵션을 만들도록 수정했다.
- 따라서 실제 기기 1대면 LEVEL 드롭다운도 아래처럼만 보여야 한다.
  - `모든 기기`
  - `LS21-3456`

### 20.7 지역코드 / 식별 기준 최신 원칙
- `LS21` 은 고정된 지역코드가 아니다.
- 지역코드는 지역마다, 기기마다 달라질 수 있다.
- 따라서 이제부터 `서울`, `인천` 같은 표시명은 식별 기준으로 사용하지 않는다.
- 식별과 정규화의 기준은 raw `region_code + device_code` 이다.
- 한글 지역명 토픽은 legacy 호환용으로만 취급하고, Node-RED 내부 canonical key 는 raw region code 기준으로 유지한다.

### 20.8 최근 반영 파일
- Node-RED live flow:
  - `code/2025123003_nodered.json`
- 실기기 Pico 코드:
  - `gswater_python/gswater_python/app.py`
  - `gswater_python/gswater_python/main.py`
  - `gswater_python/gswater_python/mqtt_bridge_pico.py`
  - `gswater_python/gswater_python/umqtt/simple.py`

### 20.9 최근 검증 메모
- 실기기 MQTT 샘플 수신에서 `dashboard_state`, `water_level`, `battery`, `solar_control`, `network_control` 발행을 확인했다.
- LEVEL 중복 제거 로직은 `서울-3456` 와 `LS21-3456` 가 동시에 있어도 최종 옵션이 `LS21-3456` 하나로 합쳐지는 시뮬레이션으로 검증했다.
- LOG 드롭다운은 정상 동작 확인을 마쳤다.
- LEVEL 드롭다운은 로그 탭과 같은 구조로 재정리했고, 최신 반영 기준으로 빈 옵션과 중복 옵션이 나오지 않아야 한다.

## 21. 2026-04-02 LOG 탭 모바일 렌더 및 표시 기준 보정

주의:

- 이 섹션은 `20.` 이후 추가 반영된 LOG 탭 최신 상태를 기준으로 작성한다.
- 특히 모바일에서 LOG 카드가 PC와 다르게 보이거나, 시간이 지나며 카드 높이가 줄어드는 문제는 아래 기준으로 대체한다.

### 21.1 LOG 탭 데이터 표기 최신 기준
- LOG 셀 데이터 글자 크기는 현재 `10px` 이다.
- 셀 안 데이터는 두 줄이 아니라 한 줄로 표시한다.
  - 예: `가동 30`
  - 예: `CH 07`
  - 예: `SOL on`
- LOG 라벨은 아래 기준으로 축약했다.
  - `채널 -> CH`
  - `배터리 -> BAT`
  - `태양광 -> SOL`
- `모드 압력`, `모드 오뚜기` 형식은 더 이상 사용하지 않는다.
  - 현재는 `압력`, `오뚜기` 값만 표시한다.

### 21.2 LOG 탭 셀 정렬 / 프레임 기준
- 각 데이터 셀은 동일한 최소 크기 기준으로 맞춘다.
- 셀 안 텍스트는 가운데 정렬한다.
- 셀은 한 줄 표시를 유지하기 위해 줄바꿈을 허용하지 않는다.
- 넘치는 문구는 셀 내부에서 잘리지 않도록 짧은 라벨 기준으로 정리했고, 필요한 경우 ellipsis 처리한다.

### 21.3 LOG 탭 모바일 표시 기준
- 스마트폰 화면에서도 PC와 동일한 형식으로 표시한다.
- 반응형으로 `5열 -> 3열 -> 2열 -> 1열`로 바뀌던 기존 규칙은 제거했다.
- 현재는 모바일에서도 각 로그를 `5칸씩 한 줄` 구조로 고정 렌더한다.
- 마지막 줄의 데이터 수가 5개보다 적으면 빈 칸을 숨김 처리해서 정렬만 유지한다.

### 21.4 LOG 탭 렌더 구조 최신 기준
- 기존 CSS grid 의존 렌더 대신, 프런트에서 로그 데이터를 `5개씩 한 행(row)`으로 나눈 뒤 렌더하도록 바꿨다.
- `item.columns` 가 없거나 깨진 경우에도 `summary` 문자열에서 다시 셀 데이터를 복원해 행을 만든다.
- 따라서 모바일/PC 모두 같은 5열 묶음 구조를 유지해야 한다.

### 21.5 LOG 탭 잘림 / 스크롤 보정 기준
- 오른쪽 스크롤바가 마지막 열 셀을 덮지 않도록 LOG feed 우측 여백을 늘렸다.
- `overflow-y` 와 `overflow-x` 를 분리해, 세로 스크롤만 허용하고 가로 넘침은 숨긴다.
- LOG 카드 외곽 프레임 밖으로 셀이 밀려나던 문제를 줄이기 위해 셀 간격과 내부 패딩을 다시 조정했다.

### 21.6 LOG 카드 높이 수축 문제 보정
- 처음에는 모든 셀이 보이다가, 시간이 지나 로그가 쌓이면 외곽 프레임 높이가 줄어들며 아래 셀이 사라지던 문제가 있었다.
- 원인은 LOG 목록 컨테이너가 세로 `flex` 구조이고, 각 `.log-item` 카드가 기본 `shrink` 상태였기 때문이다.
- 현재는 `.log-item` 에 `flex: 0 0 auto` 를 적용해 카드가 절대 줄어들지 않도록 보정했다.
- 따라서 새 로그가 계속 쌓여도 기존 카드 높이가 유지되어야 한다.

### 21.7 이번 구간의 최신 반영 파일
- 문서 기준 최신 LOG 탭 반영은 아래 파일에 들어 있다.
  - `code/2025123003_nodered.json`

### 21.8 이번 구간의 최신 검증 메모
- LOG 탭은 현재 PC와 스마트폰 모두 `5열 기준` 유지가 목표 상태다.
- 모바일에서 셀이 프레임 밖으로 밀리던 문제에 대해 우측 스크롤 여백과 셀 폭 규칙을 재조정했다.
- 모바일에서 시간이 지나며 카드 높이가 줄어들던 문제는 `.log-item` 의 shrink 방지로 보정했다.
- 최신 검증 기준으로 Node-RED 재기동 후 `/` 와 `/ui/` 응답은 모두 `200 OK` 상태다.

## 22. 2026-04-02 로그인 / 초기 셋업 기능 상세 정리

주의:

- 이 섹션은 현재 운영 중인 로그인/셋업 기능의 최종 반영 상태를 기준으로 작성한다.
- 기준 flow 파일은 `code/2025123003_nodered.json` 이다.
- 사용자 계정 저장 파일은 `.node-red-user/user_credentials.json` 이다.

### 22.1 이번 구간의 핵심 요구사항
- 로그아웃 상태에서는 `HOME`, `Login` 탭만 보여야 한다.
- 로그아웃 상태에서 `Login` 탭에는 `Sign In` 화면만 보여야 한다.
- `admin / 0000` 입력 시에는 일반 로그인 대신 `Initial Setup` 화면으로 진입해야 한다.
- `Initial Setup` 에서 새 `ID / Password` 를 만들면 재시작 후에도 유지되어야 한다.
- `MAKE` 성공 시 자동으로 `Sign In` 화면으로 돌아가야 한다.
- `취소` 버튼은 `Sign In` 화면으로 복귀해야 한다.
- `Clear` 버튼은 입력값만 지워야 한다.
- 로그인/셋업 카드에서 좌우 스크롤이 생기지 않아야 한다.
- 로그인/셋업 카드 하단 여백은 상단 여백과 균형이 맞아야 한다.

### 22.2 현재 로그인 동작 기준
- 로그아웃 상태:
  - 보이는 탭은 `HOME`, `Login` 두 개만 유지한다.
  - `SEARCH`, `LOG`, `SEOUL`, `INCHEON`, `LEVEL`, `Dynamic Devices` 는 숨긴다.
- `HOME` 탭:
  - 로그아웃 상태에서도 정상 표시된다.
  - `HOME` 진입이 `Login` 또는 `Setup` 화면을 다시 강제로 덮어쓰지 않도록 보정했다.
- `Login` 탭:
  - 기본 상태는 항상 `Sign In` 화면이다.
  - 로그아웃 상태에서 `Login` 탭에 들어갔을 때 이전 `setup` 상태가 복원되지 않도록 했다.
- 일반 로그인:
  - `.node-red-user/user_credentials.json` 에 저장된 계정으로 로그인한다.
  - 로그인 성공 시 `HOME` 으로 이동하고, 허용된 탭만 보이게 한다.
- 초기 셋업 진입:
  - `admin / 0000` 입력 시 `Initial Setup` 화면을 띄운다.
  - 이 계정은 일반 운영 계정이 아니라 셋업 진입용 고정 경로로 사용한다.

### 22.3 계정 저장 및 유지 방식
- 저장 파일:
  - `.node-red-user/user_credentials.json`
- 저장 구조:
  - 키: 로그인 ID
  - 값:
    - `password`
    - `mqttUserID`
    - `allowedTabs`
- 계정 생성 성공 시:
  - 새 계정을 JSON 파일에 즉시 저장한다.
  - 이후 Node-RED 재기동 후에도 같은 계정으로 로그인 가능하다.
- 현재 문서 작성 시점의 저장 계정 예시는 아래 파일에 들어 있다.
  - `.node-red-user/user_credentials.json`

### 22.4 셋업 화면 동작 기준
- 진입 조건:
  - `Login` 화면에서 `admin / 0000`
- 입력 필드:
  - `Set ID`
  - `Set Password`
  - `Confirm Password`
- 버튼 동작:
  - `MAKE`
    - 세 필드가 모두 채워졌을 때만 활성화
    - 비밀번호 불일치 시 저장하지 않음
    - 같은 ID 가 이미 있으면 저장하지 않음
    - 저장 성공 시 자동으로 `Sign In` 화면 복귀
  - `취소`
    - 입력값 초기화
    - `Sign In` 화면으로 복귀
  - `Clear`
    - 입력값만 초기화
    - 셋업 화면은 유지

### 22.5 로그인 화면 동작 기준
- 입력 필드:
  - `ID`
  - `Password`
- 버튼 동작:
  - `SIGN IN`
    - 입력값이 모두 있을 때만 활성화
    - 일반 계정은 정상 인증 후 `HOME` 으로 이동
    - `admin / 0000` 은 셋업 화면으로 전환
  - `Clear`
    - 현재 입력값만 초기화
- 비밀번호 입력:
  - 브라우저의 강력한 암호 추천 기능이 끼어들지 않도록 `autocomplete`, `data-lpignore` 를 보정했다.

### 22.6 내부 상태 관리 방식
- 서버측 flow 상태:
  - `flow.current_user_id`
  - `flow.last_login_ts`
  - `flow.logout_end_time`
  - `flow.login_ui_mode`
- 브라우저 세션 상태:
  - `sessionStorage['nr_login_ui_mode_v3']`
- 전역 인증 가드:
  - `Global Auth Guard` 템플릿에서 현재 브라우저 탭이 `Login` 일 때 `login/setup` 표시 상태를 강제로 맞춘다.
  - 오래 열린 브라우저 탭도 새 빌드를 다시 받도록 build 키를 사용한다.
- 현재 최신 build 키:
  - `2026-04-02-login-fix-12`

### 22.7 주요 수정 포인트
- 로그아웃 시 `HOME`, `Login` 외 다른 탭을 숨기도록 탭 제어 로직 정리
- 로그인/셋업 전환을 group show/hide 와 브라우저 세션 상태가 충돌하지 않도록 정리
- `Restore tabs/login UI on client connect` 가 로그아웃 상태에서 `setup` 을 다시 복원하지 않도록 수정
- `Save Initial Admin Account` 성공 메시지에 명시적 topic 을 부여
  - `initial_setup_success`
  - `initial_setup_cancelled`
- 로그인 템플릿과 셋업 템플릿이 위 topic 을 받아 브라우저 세션 상태도 함께 `login` 으로 되돌리도록 수정
- `MAKE` 성공 후 `Sign In` 자동 복귀 경로를 브라우저 자동 검증으로 확인

### 22.8 레이아웃 / 스크롤 보정 기준
- 로그인 화면과 셋업 화면 모두 카드 하단의 좌우 스크롤을 제거했다.
- 가로 스크롤 원인은 다음 두 가지였다.
  - `.sx-wrap` 의 `100% + padding` 계산
  - 카드 컨테이너의 가로 overflow 허용
- 현재는 아래 기준으로 보정했다.
  - `.sx-wrap` 는 `box-sizing: border-box`
  - 로그인/셋업 카드 컨테이너는 `overflow-x: hidden`
  - 카드 바깥 여백은 최소한만 남기도록 `4px` 기준 사용
  - 내부 마진/패딩도 기존보다 줄여 프레임이 카드 안에 자연스럽게 들어가도록 조정
- 하단 여백 보정:
  - 카드가 지나치게 길어 보이던 하단 빈 영역을 줄였다.
  - 카드 높이는 콘텐츠가 잘리지 않도록 아래 값으로 최종 조정했다.
    - 로그인 템플릿 높이: `6`
    - 셋업 템플릿 높이: `7`
- 현재 기준으로:
  - 좌우 스크롤 없음
  - 카드 잘림 없음
  - 상하 여백이 균형 맞는 상태

### 22.9 관련 노드 / 파일
- flow 파일:
  - `code/2025123003_nodered.json`
- 계정 저장 파일:
  - `.node-red-user/user_credentials.json`
- 주요 노드 이름:
  - `Dashboard logged-out bootstrap`
  - `자격 증명 확인 & 타이머 설정`
  - `Save Initial Admin Account`
  - `Restore tabs/login UI on client connect`
  - `SX Login UI (Initial Setup style)`
  - `Initial Setup (Premium UI, single-frame)`
  - `Global Auth Guard`

### 22.10 검증 메모
- 브라우저 자동 검증으로 아래 흐름을 확인했다.
  - `HOME -> Login -> Sign In 표시`
  - `admin / 0000 -> Initial Setup 표시`
  - 새 계정 입력 후 `MAKE -> Sign In 자동 복귀`
  - `취소 -> Sign In 복귀`
  - `Clear -> 입력값만 초기화`
- 레이아웃 검증으로 아래도 확인했다.
  - 로그인 화면 가로 오버플로우 없음
  - 셋업 화면 가로 오버플로우 없음
  - 카드가 프레임 바깥으로 넘치지 않음
- 현재 런타임 응답 기준:
  - `/` 응답 `200 OK`
  - `/ui/` 응답 `200 OK`

## 24. 2026-04-03 fast/slow payload 분리 및 유지 전략

### 24.1 목적
- 실기기 Pico 가 약 5초마다 보내는 MQTT payload 크기를 줄인다.
- 자주 변하지 않는 설정/메타데이터는 저주기 전송으로 분리한다.
- Node-RED 는 느린 데이터가 자주 오지 않아도 마지막 수신값을 유지한다.
- 설정값이 바뀌면 1시간 주기를 기다리지 않고 즉시 반영한다.

### 24.2 최신 MQTT 토픽 구조
- 현재 기준 토픽 구조:
  - `MQTT_USER_ID/pico/관정명/토픽명`
- 예:
  - `1/pico/노원1관정/dashboard_state`
  - `1/pico/노원1관정/dashboard_meta`
  - `1/pico/노원1관정/pump_state`
  - `1/pico/노원1관정/pump_cmd`
- 예전 구조의 `.../3456/...` 기기코드는 제거했다.
- 기기 식별은 이제 `관정명` 기준이다.

### 24.3 fast payload 기준
- 주기:
  - 약 `5초`
- 토픽:
  - `.../dashboard_state`
- 본문에는 아래 7가지만 남긴다.
  - `수위` -> `data.water_level_pct`
  - `관정` -> `data.well_depth_m`
  - `전류` -> `data.current_a`
  - `유량` -> `data.flow_ton`
  - `솔라` -> `data.solar`
  - `배터리` -> `data.battery_pct`
  - `현재시간` -> `timestamp`
- 전송 최적화를 위해 아래 값은 fast payload 본문에서 제거했다.
  - `schema`
  - `region_code`
  - `device_code`
  - `display.region`
  - `data.well_name`
- 이유:
  - 토픽이 이미 `관정명` 과 데이터 종류를 표현한다.
  - 화면 표시에 필요한 정적 메타는 slow payload 또는 Node-RED 저장소에서 유지한다.

### 24.4 fast payload 실수신 예시
- 실브로커에서 확인한 현재 `dashboard_state` 예시는 아래와 같다.

```json
{
  "data": {
    "current_a": 0.0,
    "water_level_pct": 8,
    "solar": "on",
    "flow_ton": null,
    "battery_pct": 95,
    "well_depth_m": null
  },
  "timestamp": "2026-04-03T02:45:16+09:00"
}
```

### 24.5 slow payload 기준
- 토픽:
  - `.../dashboard_meta`
- 전송 시점:
  - MQTT 연결 직후 1회
  - 이후 약 `1시간`마다 재전송
  - 설정값/메타값이 바뀌면 즉시 전송
- `dashboard_meta` 에 넣는 데이터는 fast 7개를 제외한 나머지 값이다.
- 현재 코드 기준 주요 항목:
  - `channel`
  - `lte`
  - `network`
  - `version_text`
  - `horse_power`
  - `well_address`
  - `phone_numbers`
  - `pressure_enabled`
  - `stop_pct`
  - `run_pct`
  - `alarm_pct`
  - `pump`
  - `motor_install_date`
  - `battery_stage`
  - `current_date`

### 24.6 즉시 반영 조건
- BLE/앱에서 설정이 바뀌면 `service_bluetooth_updates(...)` 가 변경 여부를 반환한다.
- 변경이 있으면 `mqtt_bridge.request_publish()` 를 호출한다.
- 이때 다음 publish cycle 에서 `dashboard_meta` 가 즉시 다시 나가도록 설계했다.
- 즉시 반영 대상 예:
  - `HP`
  - `관정주소`
  - `전화번호`
  - `정지/가동/알람 임계값`
  - `설치일`
  - 기타 앱에서 수정 가능한 설정값

### 24.7 Node-RED 수신 및 유지 방식
- `Display Cards State Router` 는 이제 다음 3종을 함께 받는다.
  - `dashboard_state`
  - `dashboard_meta`
  - `pump_state`
- 처리 방식:
  - `dashboard_state`
    - fast 값 갱신
    - `updated_at` 갱신
    - 카드 live 상태 기준이 됨
  - `dashboard_meta`
    - 기존 카드 data 와 병합
    - `updated_at` 은 유지
    - 따라서 느린 메타가 자주 안 와도 카드가 지워지지 않음
  - `pump_state`
    - 펌프 상태만 별도 반영

### 24.8 Node-RED 저장소 강화
- 느린 메타가 재시작 후에도 유지되도록 아래 저장소를 file context 까지 같이 쓰도록 보강했다.
  - `flow(display_cards_store)`
  - `global(well_contact_directory)`
  - `global(phone_numbers_by_well_name)`
- 목적:
  - Node-RED 재기동 후에도 관정주소 / HP / 전화번호 등 느린 값 유지
  - fast payload 만 연속 수신돼도 카드와 로그가 메타를 계속 표시

### 24.9 LOG 탭 병합 방식
- `Store Device Logs` 는 `dashboard_state` 와 `dashboard_meta` 를 병합 상태로 저장한다.
- `dashboard_meta` 수신 시:
  - 로그 한 줄을 새로 추가하지는 않음
  - 대신 마지막 상태 필드에 병합 저장
- 결과:
  - fast 로그가 계속 들어와도 `HP`, `CH`, `LTE`, 임계값 같은 느린 데이터는 유지해서 같이 표시 가능

### 24.10 현 시점 검증 메모
- 실브로커에서 fast `dashboard_state` 실수신 확인 완료
- 대시보드 브라우저 확인 완료:
  - `HOME`: `Online Devices = 1`
  - `REGION1`: `노원1관정/문경시 충무로21`, `HP 34` 유지
  - `LOG`: fast 데이터와 느린 메타 병합 표시 확인
  - `LEVEL`: 드롭다운 `관정명/관정주소` 표시 유지
- 주의:
  - `dashboard_meta` 는 코드와 Node-RED 병합 로직은 반영 완료
  - 실브로커에서의 명시적 초기/주기 캡처는 Wi-Fi 재접속 타이밍 영향이 있어 별도 추가 확인이 필요할 수 있음

### 24.11 관련 파일
- Pico:
  - `gswater_python/gswater_python/app.py`
  - `gswater_python/gswater_python/mqtt_bridge_pico.py`
- Node-RED:
  - `code/2025123003_nodered.json`
  - `.node-red-user/settings.js`

## 23. 2026-04-02 실기기 관정 메타데이터 및 LEVEL 기간 검색 반영

### 23.1 이번 섹션의 변경 범위
- 실기기 Pico에서 올라오는 추가 메타데이터를 대시보드에 반영했다.
- 기존 `지역코드/기기코드` 중심 표시는 `관정명/관정주소` 중심으로 바꿨다.
- `LEVEL` 탭은 단순 최근 60초 실시간 그래프에서 확장하여, 시작일/종료일 기반 기간 검색이 가능하도록 수정했다.
- 이번 변경의 기준 flow 파일은 아래다.
  - `code/2025123003_nodered.json`
- 검색용 워터레벨 장기 저장을 위해 아래 설정 파일도 수정했다.
  - `.node-red-user/settings.js`

### 23.2 실기기 메타데이터 수신 기준
- 실기기 `dashboard_state` 에서 아래 필드를 수신 기준으로 사용한다.
  - `data.well_name`
  - `data.well_address`
  - `data.horse_power`
  - `data.phone_numbers`
- 현재 실기기 실수신 예시는 아래 구조다.
  - topic: `1/pico/<관정명>/<device>/dashboard_state`
  - payload:
    - `region_code`
    - `device_code`
    - `data.well_name`
    - `data.well_address`
    - `data.horse_power`
    - `data.phone_numbers`

### 23.3 관정명/전화번호 매핑 저장 기준
- 실기기 `dashboard_state` 수신 시 아래 전역 디렉터리를 유지하도록 구현했다.
  - `global.well_contact_directory`
  - `global.phone_numbers_by_well_name`
- 저장 구조:
  - `well_contact_directory.byDevice[<region_code>-<device_code>]`
  - `well_contact_directory.byWellName[<well_name>]`
- 저장 값:
  - `uid`
  - `region_code`
  - `device_code`
  - `well_name`
  - `well_address`
  - `horse_power`
  - `phone_numbers`
  - `updated_at`
- 이 구조는 이후 문자 발송 기능에서 `관정명 -> 전화번호 목록` 매핑을 바로 사용할 수 있도록 유지한다.

### 23.4 REGION1 / REGION2 탭 기준
- 예전 `서울`, `인천` 탭명은 더 이상 사용하지 않는다.
- 대시보드 지역 탭은 아래 2개만 기준으로 사용한다.
  - `REGION1`
  - `REGION2`
- 현재 라우팅 규칙:
  - 명시적으로 `REGION2`, `INCH`, `INCHEON` 으로 분류되는 경우만 `REGION2`
  - 그 외는 기본 `REGION1`
- 이 라우팅은 `dashboard_state` 기반 디스플레이 카드와 카드 snapshot 경로에 반영되어 있다.

### 23.5 REGION 카드 상단 제목 기준
- REGION 카드 상단 제목은 더 이상 `관정명/기기코드` 를 사용하지 않는다.
- 현재 우선순위:
  - `관정명/관정주소`
  - `관정명`
  - `관정주소`
  - fallback 으로만 탭명
- 따라서 예전처럼 `노원1관정/3456` 이 보이지 않고, `노원1관정/문경시 충무로21` 형식으로 표시되도록 변경했다.
- 이 제목 보정은 REGION1, REGION2 카드 템플릿 둘 다 동일하게 적용했다.

### 23.6 REGION 카드 본문 추가 반영
- 카드 하단 `모터설치` 줄에는 아래 형식을 사용한다.
  - `모터설치 <날짜> · HP <값>`
- 실기기에서 수신된 `horse_power` 를 카드에 같이 표시하도록 반영했다.
- 카드 자체 표시는 기존 UI 구조를 유지한 상태에서 텍스트만 보강했다.

### 23.7 LOG 탭 반영 기준
- LOG 저장 단계에서 `dashboard_state` 로부터 아래 필드를 추출한다.
  - `wellName`
  - `wellAddress`
  - `hp`
  - `phoneNumbers`
- LOG 화면 표시 기준:
  - `HP` 는 표시
  - `관정명` 은 화면에 표시하지 않음
  - `관정주소` 와 `전화번호` 는 summary / 내부 저장에는 포함될 수 있음
- LOG 드롭다운 라벨은 아래 우선순위를 사용한다.
  - `관정명/관정주소`
  - `관정명`
  - `관정주소`
  - fallback: 기존 device key
- 내부 선택값은 기존 canonical key 를 유지하고, 화면 표시용 label 만 `관정명/관정주소` 로 바꿨다.

### 23.8 LEVEL 탭 장치명 표시 기준
- LEVEL 드롭다운도 LOG 와 동일하게 화면 표시 label 을 아래 우선순위로 맞췄다.
  - `관정명/관정주소`
  - `관정명`
  - `관정주소`
  - fallback: canonical device key
- 내부 선택값은 기존 canonical key 를 그대로 유지한다.
- 차트 범례(series) 역시 내부 key 가 아니라 display label 을 사용하도록 수정했다.
- 따라서 예전처럼 `노원1관정-3456` 이 보이지 않고, `노원1관정/문경시 충무로21` 형식으로 표시된다.

### 23.9 LEVEL 탭 기간 검색 기능
- LEVEL 탭 상단에 아래 필터를 추가했다.
  - `시작일`
  - `종료일`
  - `조회`
  - 기존 기기 선택 드롭다운
- 사용 방식:
  - 시작일 입력
  - 종료일 입력
  - 필요 시 드롭다운에서 기기 선택
  - `조회` 버튼 클릭
- 검색 결과:
  - 선택 기기가 있으면 해당 기기의 워터레벨 그래프만 표시
  - 기기를 선택하지 않으면 범위 내 전체 기기 그래프 표시
- 날짜를 비워두면 기존처럼 최근 실시간 데이터 기준으로 동작한다.

### 23.10 LEVEL 기간 검색의 저장 방식
- 기존 LEVEL 그래프는 최근 60초 메모리 데이터만 유지했다.
- 1년 검색을 위해 워터레벨 이력을 별도 장기 저장 경로로 추가했다.
- 저장 키:
  - `flow(level_water_archive_by_device)` + file context
- 저장 단위:
  - `10분 bucket`
- 보존 기간:
  - 최대 `366일`
- 저장 목적:
  - 실시간 렌더 성능을 유지하면서도 장기 검색 가능하게 하기 위함
- 현재 워터레벨 검색용 파일 컨텍스트 저장은 아래 key 로 확인했다.
  - `level_water_archive_by_device`

### 23.11 Node-RED contextStorage 변경
- `.node-red-user/settings.js` 에 아래 context storage 를 활성화했다.
  - `default: memory`
  - `file: localfilesystem`
- 목적:
  - LEVEL 장기 검색용 워터레벨 이력을 디스크에 유지
  - Node-RED 재시작 후에도 기간 검색 가능
- 현재 기동 로그에서 아래가 확인된다.
  - `Context store  : 'default' [module=memory]`
  - `Context store  : 'file' [module=localfilesystem]`

### 23.12 LEVEL 기간 검색 제한 규칙
- 검색 최대 기간은 `1년` 이다.
- 시작일/종료일 중 하나만 입력하면 같은 날짜로 보정한다.
- 시작일이 종료일보다 뒤면 자동으로 순서를 교환한다.
- 기간이 1년을 초과하면 종료일을 자동 보정하고 안내 문구를 표시한다.
- 안내 문구 기본값:
  - `최대 1년 검색`
- 1년 초과 시 안내 문구:
  - `최대 1년까지만 조회됩니다.`

### 23.13 차트 렌더링 기준
- `Water Level (%)` 차트는 범위 검색도 그릴 수 있도록 x축 포맷을 아래로 조정했다.
  - `YY-MM-DD HH:mm`
- 차트 자체의 유지 시간 설정도 확장했다.
  - `removeOlder: 366`
  - `removeOlderUnit: 86400`
- 검색 범위 데이터는 과도하게 많아지는 것을 방지하기 위해 downsampling 후 렌더한다.
- 현재 범위 검색용 최대 렌더 포인트 수:
  - `1200`

### 23.14 관련 노드 / 파일
- flow 파일:
  - `code/2025123003_nodered.json`
- 설정 파일:
  - `.node-red-user/settings.js`
- 주요 노드:
  - `Display Cards State Router`
  - `Display Cards UI Bridge`
  - `Store Device Logs`
  - `Build LOG tab view`
  - `LEVEL chart input normalize`
  - `LEVEL Device Filter`
  - `LEVEL chart store + build`
  - `Water Level Chart`

### 23.15 검증 메모
- 실기기 메타데이터 반영 확인:
  - `well_name`
  - `well_address`
  - `horse_power`
  - `phone_numbers`
- REGION 카드 제목 함수 보정 확인:
  - `관정명/관정주소`
- LOG 드롭다운 label 보정 확인:
  - `관정명/관정주소`
- LEVEL 드롭다운 label 보정 확인:
  - `관정명/관정주소`
- LEVEL 차트 legend 보정 확인:
  - `관정명/관정주소`
- 파일 컨텍스트 생성 확인:
  - `.node-red-user/context/73a3c4ea7bfb6ad2/flow.json`
- 파일 컨텍스트 키 확인:
  - `level_water_archive_by_device`
- 함수 시뮬레이션 확인:
  - 기간 `2026-03-01 ~ 2026-03-31`
  - 장치 label `노원1관정/문경시 충무로21`
  - 차트 포인트 3개 반환
- 현재 런타임 응답 기준:
  - `/` 응답 `200 OK`
  - `/ui/` 응답 `200 OK`

## 25. 2026-04-03 OLAX LTE / 외부 접속 / 포트포워딩 현행 정리

### 25.1 OLAX 라우터 LTE 상태 확인 결과
- 사용 라우터:
  - `OLAX-4G-DC75`
- 로컬 관리자:
  - `http://192.168.0.1`
- 라우터 상태 API 로그인 후 확인 결과:
  - `network_type: LTE`
  - `sub_network_type: FDD_LTE`
  - `ppp_status: ppp_connected`
  - `signalbar: 5`
  - `simcard_roam: Home`
  - `wan_apn: lte.sktelecom.com`
- 결론:
  - OLAX 라우터는 실제로 `LTE/4G 망에 붙어 있음`
  - 단, 특정 시점의 실데이터 미수신 원인은 라우터 WAN 자체보다 `피코 MQTT publish 쪽`에 더 가까웠음

### 25.2 현재 네트워크 인터페이스 정리
- 맥북 사무실 Wi-Fi:
  - `en0 = 192.168.1.186`
- 맥북 USB LAN:
  - `en5 = 192.168.1.197`
- OLAX USB NIC:
  - `en7 = 192.168.0.100`
- 피코가 OLAX 쪽에 붙을 때 확인된 주소:
  - `192.168.0.101`
- 기본 route 확인 시점 기준:
  - 기본 경로는 `en5` 를 타고 있었음
- 따라서 포트포워딩과 외부 공개 주소는 `192.168.1.197` 기준으로 맞추는 것이 안전함

### 25.3 현재 확인된 MQTT 실제 구조
- `Node-RED` 현재 외부 MQTT 연결:
  - `192.168.1.197 -> 44.232.241.40:1883`
- 현재 시점 맥북 로컬 `1883` 상태:
  - `LISTEN 아님`
  - `127.0.0.1:1883` 접속 시 `Connection refused`
- 현재 시점에서 실제로 확인된 구조:
  - `피코 -> OLAX 라우터(4G) -> 인터넷 -> 외부 MQTT broker`
  - `Node-RED(맥북) -> 사무실망 -> 인터넷 -> 같은 외부 MQTT broker`
- 따라서 이 시점 기준으로는:
  - `공유기 포트포워딩 -> 맥북 로컬 MQTT` 구조가 실제 활성 구조는 아니었음
  - `외부 MQTT broker` 구조가 실사용 경로였음

### 25.4 외부 MQTT 경로 진단 메모
- 외부 브로커 전체 구독 확인:
  - `1/pico/#`
- 특정 시점 실수신 결과:
  - `TOTAL 0`
- 라우터에는 Wi-Fi station 1대가 붙어 있음:
  - `sta_count: 1`
- 해석:
  - 피코는 라우터 AP 까지는 붙어 있었으나, 당시에는 MQTT publish 를 못 하고 있었음
- 해당 시점 판단:
  - `라우터 LTE 붙음`
  - `Node-RED 정상`
  - `실피코 publish 중단`

### 25.5 ipTIME 포트포워딩 판단 기준
- 사용자가 ipTIME A2004MU에 아래 규칙을 등록함:
  - `mqtt -> 192.168.1.197, TCP 1883 -> 1883`
  - `nodered -> 192.168.1.197, 외부 1883 -> 내부 1880`
- 이 상태는 잘못된 구성임
  - 같은 `외부 포트 1883` 를 두 규칙이 동시에 사용하면 충돌함
- 올바른 기준:
  - `mqtt`
    - 외부 `1883 -> 내부 1883`
  - `nodered`
    - 외부 `1880 -> 내부 1880`
- 추가 주의:
  - 로컬 MQTT 브로커를 실제로 맥북에서 띄우지 않으면 `1883` 포워딩만으로는 동작하지 않음
  - `외부 MQTT broker` 구조를 유지한다면, 스마트폰에서 대시보드 보기 목적에는 `1880`만 필요함

### 25.6 스마트폰 LTE 대시보드 접속 기준
- 공인 IP 확인 시점:
  - `180.67.220.176`
- 외부 확인:
  - `http://180.67.220.176:1880/ui/` 응답 `200 OK`
  - `http://180.67.220.176:1880/` 응답 `200 OK`
- 스마트폰 LTE 접속 주소:
  - `http://180.67.220.176:1880/ui/`
- 로그인:
  - `aaa / 1111`
- 주의:
  - `1880`을 외부 공개하면 `Node-RED 편집기(/)` 도 같이 열릴 수 있음
  - 장기적으로는 `VPN`, `Cloudflare Tunnel`, 또는 편집기 접근 제한이 필요함

### 25.7 로컬 MQTT / 외부 MQTT 선택 기준
- `외부 MQTT broker 유지`
  - 장점:
    - 포트포워딩 없이도 피코와 맥북이 서로 다른 인터넷망에서 broker 에서 만남
  - 요구 사항:
    - 피코가 외부 broker 로 publish 가능해야 함
- `맥북 로컬 MQTT 사용`
  - 요구 사항:
    - 맥북에서 `1883` 브로커 실행
    - 공유기 포트포워딩 `1883 -> 192.168.1.197:1883`
    - 피코 서버 주소를 공유기 공인 IP 또는 DDNS 로 설정
- 현행 런타임은 `외부 MQTT broker` 기준으로 정리되어 있음

### 25.8 관련 검증 명령 메모
- 공인 IP 확인:
  - `curl -s https://api.ipify.org`
- 외부 대시보드 확인:
  - `curl -I http://180.67.220.176:1880/ui/`
- 맥북 로컬 1883 확인:
  - `lsof -nP -iTCP:1883 -sTCP:LISTEN`
- Node-RED 외부 MQTT 연결 확인:
  - `lsof -nP -iTCP -sTCP:ESTABLISHED | rg '1883|node-red'`
- OLAX 상태 확인:
  - `/goform/goform_get_cmd_process`

### 25.9 최신 백업
- 현재 기준 최신 백업:
  - `nodered_backup_20260403_152710.tar.gz`

## 26. 2026-04-06 REGION1 드롭다운 검색 추가

### 26.1 변경 목적
- `REGION1` 탭에서 카드 제목(예: `노원1관정/문경시 충무로21`) 위에 검색용 드롭다운을 추가했다.
- 사용자가 다수 관정 카드 중 원하는 관정을 빠르게 찾을 수 있도록 하기 위한 변경이다.
- 요청 조건:
  - 드롭다운 형식
  - `LEVEL` 탭과 같은 시각적 스타일
  - 날짜 범위 없음
  - 관정명 기준 `가나다 순` 정렬
  - 다른 기능과 UI는 유지

### 26.2 반영 파일
- `code/2025123003_nodered.json`

### 26.3 구현 위치
- `REGION1` 카드 템플릿 노드:
  - `id: ea2415d427733733`
  - 기존 이름: `DISPLAY CARDS / SEOUL`
- 수정 위치:
  - `format` 문자열 내부 CSS
  - `format` 문자열 내부 HTML 마크업
  - `format` 문자열 내부 AngularJS 스크립트

### 26.4 UI 변경 내용
- `REGION1` 카드 목록 상단에 드롭다운 검색창을 추가했다.
- 드롭다운은 `LEVEL` 탭 셀렉트와 같은 입력창 스타일을 따르도록 맞췄다.
- 추가한 클래스:
  - `.dc-filter-shell`
  - `.dc-filter-wrap`
  - `.dc-filter-select`
- 드롭다운 기본 항목:
  - `모든 기기`

### 26.5 동작 방식
- 수신된 `display_cards_snapshot`에서 `REGION1` 카드 목록을 그대로 받아온다.
- 카드 제목/관정명 계산은 기존 카드 데이터 구조를 유지한 채 템플릿 내부에서 처리한다.
- 드롭다운 옵션은 카드 목록으로부터 동적으로 생성한다.
- 선택값이 없으면 `REGION1` 카드 전체를 그대로 표시한다.
- 특정 관정을 선택하면 해당 카드만 표시한다.
- 기존 카드 렌더링 로직, 펌프 버튼, stale 처리, snapshot 요청 주기 등은 그대로 유지한다.

### 26.6 정렬 기준
- 옵션 정렬 기준은 카드 제목 전체가 아니라 `관정명`이다.
- 정렬 함수:
  - `localeCompare(..., 'ko', { numeric: true, sensitivity: 'base' })`
- 목적:
  - 관정명 기준 `가나다 순` 정렬
  - 숫자 포함 이름도 자연스럽게 찾을 수 있도록 함

### 26.7 확장 고려 사항
- 다른 REGION 탭에도 같은 구조를 그대로 확장할 수 있도록 템플릿 내부 함수를 일반화했다.
- REGION1 내부에 추가한 함수:
  - `cardWellName(card)`
  - `cardTitle(card)`
  - `buildFilterOptions(cards)`
  - `applyCardFilter()`
  - `selectRegionCard()`
- 이 구조는 다른 REGION 카드 템플릿에도 거의 그대로 복사해 적용할 수 있다.
- 즉, 이번 변경은 `REGION1`에만 적용했지만, `REGION2` 이상으로 확장하기 쉽게 작성했다.

### 26.8 데이터 구조 영향 범위
- 백엔드 function 노드 추가 없음
- MQTT 토픽 구조 변경 없음
- 카드 payload 구조 변경 없음
- `REGION1` 템플릿 내부 렌더링/필터링만 변경

### 26.9 검증 결과
- 저장 파일 JSON 파싱 정상 확인
- live Node-RED `/flows` 재배포 완료 (`204`)
- live flows 안에 아래 문자열이 실제 반영된 것 확인:
  - `dc-filter-shell`
  - `selectedCardKey`
  - `selectRegionCard()`
  - `ng-repeat=\"card in filteredCards`
  - `localeCompare(..., 'ko', ...)`
- `/ui/` 응답 `200 OK` 확인

### 26.10 운영 메모
- 현재 브라우저에 이전 템플릿 캐시가 남아 있으면 `REGION1` 탭 새로고침이 필요할 수 있다.
- 향후 `REGION2`, 추가 REGION 탭에도 동일 검색 UX가 필요하면 같은 템플릿 패턴으로 확장하면 된다.

## 27. 2026-04-06 동시 접속 세션 분리

### 27.1 변경 목적
- 여러 사용자가 동시에 대시보드에 접속해도 서로 로그인 상태, 탭 상태, 검색 상태, 로그/레벨 선택 상태가 영향을 주지 않도록 세션 단위로 분리했다.
- 기존 구현은 `flow.current_user_id` 중심의 전역 상태를 사용하고 있어서, 마지막 로그인 사용자 기준으로 다른 브라우저 화면이 같이 바뀌는 구조였다.
- 이번 변경 목표는 다음과 같다.
  - 같은 계정으로 여러 탭/브라우저 접속 시 서로 로그아웃 간섭이 없을 것
  - 다른 계정이 동시에 접속해도 REGION/LOG/LEVEL/HOME 표시가 섞이지 않을 것
  - 기존 UI와 탭 구조는 유지할 것

### 27.2 핵심 구조 변경
- 로그인 상태 저장 기준을 `flow.current_user_id` 하나에서 `flow.dashboard_sessions[socketid]` 구조로 변경했다.
- 세션 저장 기본 필드:
  - `uid`
  - `loginUiMode`
  - `lastLoginTs`
  - `updatedAt`
- 세션별 상태 저장 키:
  - `dashboard_sessions`
  - `log_selected_device_by_session`
  - `level_selected_device_by_session`
  - `level_range_filter_by_session`
  - `filteredDevicesBySession`
  - `filterModeBySession`
  - `last_search_by_session`
  - `ui_active_tab_by_socket`

### 27.3 반영 파일
- `code/2025123003_nodered.json`

### 27.4 수정한 주요 노드
- 로그인/로그아웃/세션 복원
  - `b7c5d3e9f102468a` `Dashboard logged-out bootstrap`
  - `dad3e7026188e38f` `Save Initial Admin Account`
  - `4f1335340cfdf708` `로그아웃 로직`
  - `40845bc68c38af27` `자격 증명 확인 & 타이머 설정`
  - `a1f58d4b7e2c4019` `Restore tabs/login UI on client connect`
- HOME 상태 계산
  - `afc962e0866c28ef` `HOME: liveCount -> session_status (1s)`
- REGION 카드 출력
  - `6e31f4f0a8b14c01` `Display Cards State Router`
  - `6e31f4f0a8b14c02` `Display Cards UI Bridge`
- LOG 탭
  - `log_store_e5f60718` `Store Device Logs`
  - `log_build_294a5b6c` `Build LOG tab view`
- LEVEL 탭
  - `level_chart_build_c0ffee1122334455`
  - `level_tab_refresh_8899aabbccddeeff`
- SEARCH / 보조 강제 렌더 / 컨트롤 패널
  - `726c3979f864044b` `Search Dispatcher (ONLY live devices)`
  - `8997e83a3f628d6e` `Re-render (ONLY live devices, no fallback)`
  - `2fb098b0eb6d4eab` `Build Region Options (ONLY live devices)`
  - `0a6b1f2ab1d711cd` `On SEARCH tab enter: clear + rerun last search`
  - `5cc882df780943e1` `Watchdog: timeout -> clear device values (null) + UI push`
  - `6772a4a2a626668a` `Force render (TEXT region, latest if online, defaults if stale)`
  - `5d4d1239d817a36f` `Force Panel OFF if device stale (by lastSeenMs) [SAFE ROUTE]`
  - `d3f7c045aec288b1` `Auto register + (control_status -> UI) [TOPIC PARSE + ROBUST + CACHE]`
  - `fix_led_dispatcher` `FIX Dispatcher (ui_ready_all + toggle) [ONLINE-GATED + FAST CACHE + control_cmd]`

### 27.5 변경 내용
- 로그인 성공 시:
  - 전역 사용자 상태를 덮어쓰지 않고 현재 `socketid`에만 `uid`를 기록한다.
  - `session_status`도 세션 대상 브라우저에만 보낸다.
- 로그아웃 시:
  - 현재 `socketid` 세션만 제거한다.
  - LOG/LEVEL/SEARCH 관련 선택 상태도 해당 세션 것만 제거한다.
  - 다른 브라우저 세션의 로그인 상태는 유지한다.
- HOME:
  - 접속 중인 모든 세션을 순회하며, 각 세션 사용자 기준으로 `liveCount`를 따로 계산한다.
- REGION 카드:
  - 카드 snapshot을 모든 사용자에게 한 번에 뿌리지 않고, 세션별 허용 owner 기준으로 필터링한 snapshot만 보낸다.
- LOG:
  - 장비 로그 저장은 사용자별 저장소를 유지하되, 선택 상태는 `socketid` 기준으로 분리했다.
  - 같은 계정으로 두 명이 들어와도 서로 다른 장비를 선택할 수 있게 바꿨다.
- LEVEL:
  - 드롭다운 선택과 기간 검색 상태를 `socketid` 기준으로 분리했다.
  - 같은 계정으로 여러 창을 띄워도 서로 다른 장비/기간을 유지한다.
- SEARCH:
  - 검색 모드, 마지막 검색 조건, 활성 탭 상태를 세션별로 분리했다.
- 보조 렌더/컨트롤:
  - 오프라인 강제 클리어, 주기적 강제 렌더, 컨트롤 패널 상태 표시도 owner -> session 매핑을 거쳐 해당 브라우저에만 전달되도록 수정했다.

### 27.6 유지한 점
- 로그인 UI, 탭 구성, 카드 UI, LOG/LEVEL UI 마크업은 유지했다.
- 사용자 계정 파일 구조(`user_credentials.json`)는 변경하지 않았다.
- MQTT 토픽 구조와 대시보드 표시 기준은 기존 최신 상태를 그대로 유지했다.

### 27.7 검증 결과
- 수정된 `code/2025123003_nodered.json` JSON 파싱 정상 확인
- live Node-RED `/flows` 재배포 완료 (`POST /flows -> 204`)
- `/ui/` 응답 `200 OK` 확인
- 실제 브라우저 2세션 검증:
  - 같은 계정 `aaa / 1111`로 두 세션 동시 로그인
  - 세션1 로그아웃 후 세션2 유지 여부 확인
  - 결과:
    - 세션1: 로그인 화면으로 전환
    - 세션2: 로그인 화면으로 튕기지 않음
    - 세션2: `REGION1` 화면 유지
- 자동 검증 결과 값:
  - `page1_login_visible_after_logout = true`
  - `page2_login_visible_after = false`
  - `page2_region1_visible = true`

### 27.8 운영 메모
- 전역 flow 키 `current_user_id`, `login_ui_mode`, `logout_end_time`, `last_login_ts`는 로그인 초기화 호환용 흔적으로 일부 남아 있지만, 실질적인 대시보드 동작은 세션 저장소를 기준으로 한다.
- 향후 추가 탭/기능을 붙일 때도 사용자 상태나 선택 상태는 `socketid` 기준으로 저장해야 다중 접속 간섭이 생기지 않는다.

## 28. 2026-04-06 팬 클릭 릴레이 진단 및 관정 수위 표시 의미

### 28.1 목적
- REGION 카드의 fan 이미지를 클릭했을 때 실제 보드 릴레이가 동작하지 않는 원인을 확인했다.
- 관정 값이 `xxxx`로 보이는 의미를 코드 기준으로 정리했다.
- 알람 원인 수신은 유지하되, 화면에는 노출하지 않는 현재 정책을 문서화했다.

### 28.2 fan 클릭 제어 경로
- REGION 카드 fan 버튼 클릭 시:
  - `DISPLAY CARDS / SEOUL`, `DISPLAY CARDS / INCHEON` 템플릿에서 `toggle_pump` 메시지를 보낸다.
- Node-RED 브리지:
  - `6e31f4f0a8b14c02` `Display Cards UI Bridge`
  - `toggle_pump`를 받아 MQTT 토픽 `uid/pico/region_code/pump_cmd` 로 변환한다.
  - MQTT 출력 노드:
    - `85c3622a01c79c17` `MQTT OUT pump_cmd`
- Pico:
  - `mqtt_bridge_pico.py`의 `_on_message()`가 `pump_cmd`를 수신한다.
  - 유효한 명령이면 `pump_override`를 `on/off`로 설정한다.
  - `app.py`의 `service_runtime()`가 `pump_override`를 우선 반영해 `pump_active`를 결정한다.
  - `app.py`의 `update_relays()`가 최종적으로:
    - `set_relay1_panel_HI_LO(...)`
    - `set_relay2_motor(...)`
    를 호출한다.

### 28.3 현재 릴레이가 동작하지 않는 직접 원인
- 현재 런타임 저장 상태 기준:
  - `well_level_lockout: true`
  - `relay3_alarm: true`
  - `relay3_alarm_reason: "WELL|LOW"`
- 이 상태에서는 fan 클릭으로 `pump_override = on` 이 들어와도, `update_relays()`에서 보호 로직이 우선 적용되어 릴레이 1/2를 강제로 `0`으로 내린다.
- 즉 현재 증상은:
  - 클릭 이벤트 불능이 아니라
  - 관정 수위 락아웃 + 저수위 알람 때문에 릴레이 출력이 차단되는 상태다.

### 28.4 관정 수위 표시 규칙
- `build_well_level_text()` 기준:
  - `0.2V 이하` -> `xxxx`
  - `0.2V 초과, 0.4V 미만` -> `----`
  - `0.4V 이상` -> `###M`
- 의미:
  - `xxxx`: 관정 수위 센서 미연결 또는 입력 전압이 거의 0인 상태
  - `----`: 센서는 연결돼 있으나 유효 측정 범위 이하
  - `###M`: 정상 관정 수위

### 28.5 알람 원인 표시 정책
- `relay3_alarm_reason`는 Node-RED에서 계속 수신하고 내부 저장도 유지한다.
- 다만 현재 운영 UI 정책은 다음과 같다.
  - REGION 카드: 표시하지 않음
  - LOG 탭: 표시하지 않음
- 같은 방식으로 `pump_state.result`도 LOG 화면에는 표시하지 않도록 정리했다.

### 28.6 확인한 코드 위치
- Node-RED:
  - `code/2025123003_nodered.json`
  - `6e31f4f0a8b14c02` `Display Cards UI Bridge`
  - `85c3622a01c79c17` `MQTT OUT pump_cmd`
- Pico:
  - `gswater_python/gswater_python/mqtt_bridge_pico.py`
  - `gswater_python/gswater_python/app.py`

### 28.7 운영 메모
- 릴레이를 다시 수동 제어하려면 먼저 `well_level_lockout`이 해제되어야 한다.
- 현재 `xxxx`는 단순 표시 문제가 아니라, 릴레이 차단의 직접 원인 후보다.
- 안전 로직을 깨지 않고 운영하려면 센서 입력 상태와 관정 수위 전압을 먼저 정상화하는 것이 우선이다.

## 29. 2026-04-06 SOLAPI 문자 발송 설정 정리

### 29.1 목적
- 배터리 기반 문자 조건을 제거하고, `LOW/WELL` 알람 기반 문자 발송 구조만 유지하도록 정리했다.
- SOLAPI 키/시크릿/발신번호를 런타임에서 직접 읽을 수 있는 로컬 설정 파일 구조로 바꿨다.
- 피코 설정 전화번호를 최신 운영 번호로 변경하고, 즉시 재발송 검증까지 수행했다.

### 29.2 현재 문자 발송 조건
- 발송 조건:
  - `LOW`: `water_level_pct <= alarm_pct`
  - `WELL`: `well_depth_m <= 3`
- 발송 제외:
  - `COMM`
- 발송 정책:
  - 정상 -> 알람 진입 시 1회
  - 동일 조건 유지 시 24시간 후 다시 1회
- 알람 상태 저장 키:
  - `sms_alert_meta_by_well`
  - `sms_alert_state_by_well`
- 저장 위치:
  - `.node-red-user/context/73a3c4ea7bfb6ad2/flow.json`

### 29.3 문자 본문 규칙
- 형식:
  - `관정명 / 알람원인 / 관정주소`
- 예:
  - `노원1관정 / 탱크 저수위 / 문경시 충무로21`
- 알람원인 매핑:
  - `LOW` -> `탱크 저수위`
  - `HIGH` -> `탱크 고수위`
  - `WELL` -> `관정 저수위`
  - `COMM` -> 발송 안 함

### 29.4 SOLAPI 설정 파일 구조
- 파일:
  - `.node-red-user/solapi-config.local.json`
- 사용 필드:
  - `SOLAPI_KEY`
  - `SOLAPI_SECRET`
  - `SOLAPI_FROM`
- 운영 원칙:
  - 실제 키/시크릿 값은 이 문서에 기록하지 않는다.
  - Function node는 `env.get(...)` 우선, 없으면 `solapi-config.local.json` fallback으로 읽는다.

### 29.5 Node-RED 문자 노드 구조
- `70e1666a5fd4738a`
  - `SMS trigger evaluator (LOW/WELL + phones)`
  - `dashboard_state`를 받아 `LOW/WELL` 조건과 24시간 재발송 기준을 계산한다.
- `6fe3f9edc75b5b86`
  - `SOLAPI SMS builder (well phones + alarm reason)`
  - SOLAPI HMAC 서명을 생성하고 `messages/v4/send-many/detail`로 요청한다.
- `62462b30a84eb31a`
  - `ENV sanity (true/false only)`
  - 키/시크릿/발신번호 유무를 확인한다.

### 29.6 crypto 전역 컨텍스트 보강
- SOLAPI HMAC 서명을 위해 `.node-red-user/settings.js`의 `functionGlobalContext`에 `crypto: require('crypto')`를 추가했다.
- 이 변경 후 Function node에서 `global.get('crypto')`가 가능해졌다.

### 29.7 피코 전화번호 설정 변경
- 파일:
  - `gswater_python/gswater_python/config.txt`
- 실제 보드 `/dev/cu.usbmodem11101`에도 동일하게 반영함.
- 현재 설정:
  - `PHONE1`: `010-5664-8540`
  - `PHONE2`: `010-9397-8621`
  - `PHONE3`: `010-9786-0000`
  - `PHONE4`: 비움
  - `PHONE5`: 비움

### 29.8 발신번호 변경
- 발신번호를 `010-5664-8540`에서 `010-9786-0000`으로 변경했다.
- 현재 실제 발송 시 `SOLAPI_FROM`은 `01097860000`으로 사용된다.

### 29.9 실제 발송 검증
- `LOW` 상태를 수동으로 초기화한 뒤 현재 조건으로 즉시 재발송을 2회 검증했다.
- 최신 성공 발송 기준:
  - 수신번호 3건 등록 성공
  - 발신번호: `010-9786-0000`
  - 문구: `노원1관정 / 탱크 저수위 / 문경시 충무로21`
  - SOLAPI 응답: `200`
  - 메시지 그룹 상태: `SENDING`
- 검증 후 `LOW` 상태는 다시 발송 완료 시각으로 갱신해 중복 발송을 막았다.

### 29.10 운영 메모
- 실제 발송이 실패하면 `LOW` 상태를 발송 완료로 남기지 않도록 되돌리는 방식으로 처리했다.
- 발송 테스트 시에는 `sms_alert_state_by_well['노원1관정'].LOW`를 초기화한 뒤 다시 발송하면 된다.
- 현재 Node-RED는 외부 MQTT를 통해 데이터를 받고, 문자 발송만 SOLAPI HTTPS API를 사용한다.

## 30. 2026-04-06 REGION 카드 검색 UI 통일

### 30.1 목적
- `REGION1` 탭 상단에 관정명 직접 입력 검색창을 추가했다.
- `REGION2`도 같은 카드 레이아웃과 같은 검색 UI를 사용하도록 통일했다.
- 이후 `REGION3`, `REGION4` 등 다른 REGION 탭이 추가되더라도 같은 템플릿 패턴을 복제해 쉽게 확장할 수 있도록 정리했다.

### 30.2 REGION1 검색창
- 위치:
  - 드롭다운 바로 위
- 형식:
  - LEVEL 탭과 같은 스타일의 검색 입력 UI
- placeholder:
  - `관정명 빠른 검색`
- 동작:
  - 관정명 부분 문자열 검색
  - 초성 검색 지원
    - 예: `ㄴ` 입력 시 `노원1관정` 검색 가능
- 드롭다운 옵션 정렬:
  - 관정명 기준 `ko localeCompare`
  - `가나다 순`

### 30.3 REGION2 동일 레이아웃 적용
- `DISPLAY CARDS / INCHEON` 템플릿을 `DISPLAY CARDS / SEOUL`과 같은 구조로 맞췄다.
- 통일된 항목:
  - 검색 입력창
  - 드롭다운
  - 카드 상단/상태/하단 레이아웃
  - 팬 버튼 배치
  - 관정명/관정주소 제목 표시
  - 관정명 기준 정렬 및 초성 검색

### 30.4 드롭다운/검색 표시 조건
- 현재 정책:
  - 검색 입력창은 표시
  - 드롭다운은 `filterOptions.length`가 있을 때만 표시
- 의미:
  - 해당 REGION에 카드 데이터가 없으면 드롭다운은 숨김
  - 데이터가 1건 이상 들어오면 드롭다운이 표시됨

### 30.5 확장 기준
- 현재 `DISPLAY CARDS / SEOUL`, `DISPLAY CARDS / INCHEON` 두 템플릿이 같은 패턴을 사용한다.
- 새 REGION 탭을 만들 때는 다음만 바꿔 복제하면 된다.
  - `REGION_DISPLAY`
  - `BOARD_ID`
  - 탭/그룹 연결값
- 검색/정렬/초성 검색 로직은 그대로 재사용 가능하다.

### 30.6 관련 파일
- `code/2025123003_nodered.json`

### 30.7 검증
- 플로우 재배포 응답:
  - `204`
- 대시보드 응답:
  - `/ui/` `200`
- JSON 내부 확인:
  - `DISPLAY CARDS / SEOUL` 검색창 포함
  - `DISPLAY CARDS / INCHEON` 검색창 포함
  - 두 템플릿 모두 `관정명 빠른 검색`, `dc-filter-shell`, `dc-search-input` 반영 확인


## 31. 2026-04-06 팬 수동 제어와 피코 디스플레이 아이콘 동기화

### 31.1 증상
- 대시보드 REGION 카드에서 팬 버튼을 눌렀을 때 대시보드 팬 이미지는 회전하지만, 피코 DGUS 디스플레이의 펌프 아이콘은 즉시 따라오지 않는 증상이 있었다.
- 특히 `off`는 반영되는데 `on`일 때 보드 디스플레이 아이콘이 회전하지 않는 것으로 관찰됐다.

### 31.2 원인 분리
- 1차 원인:
  - 피코보드가 중간에 `>>>` REPL 상태에 멈춰 있었고, 이때는 앱 런타임이 계속 돌지 않아 MQTT 명령을 지속적으로 처리하지 못했다.
- 2차 원인:
  - 수동 `pump_override == "on"` 분기에서 DGUS `PUMP_ICON`을 자동 모드와 같은 점멸/회전 경로가 아니라 정적 icon 처리로 다루고 있었다.
- 대시보드/Node-RED 자체의 `pump_cmd` 발행 경로는 정상임을 별도 검증했다.

### 31.3 Pico 코드 수정
- 파일:
  - `gswater_python/gswater_python/app.py`
- 변경 내용:
  - `service_runtime()`의 수동 `pump_override == "on"` 분기에서 다음 경로를 사용하도록 수정했다.
    - `update_pump_blink_state(..., True, now_ms)`
    - `service_pump_blink(..., now_ms)`
  - 즉, 수동 ON도 자동 ON과 동일하게 `PUMP_ICON`이 점멸/회전 경로를 타도록 보강했다.
- 수동 `off`는 계속 정적 `PUMP_ICON=0` 경로를 유지한다.

### 31.4 Node-RED 보강
- 파일:
  - `code/2025123003_nodered.json`
- 변경 내용:
  - REGION 카드 팬 버튼에 `type="button"`을 부여했다.
  - 클릭 시 `$event.preventDefault(); $event.stopPropagation();`를 적용해 브라우저 기본 동작 간섭을 막았다.
  - `pump_cmd` payload의 `region_code`가 비어도 `display_region` 또는 관정명 fallback으로 채워지도록 보강했다.

### 31.5 실제 검증 결과
- 외부 MQTT 브로커에서 직접 검증:
  - `1/pico/노원1관정/pump_cmd` 발행 시 Pico가 `MQTT pump_cmd -> on/off`를 실제로 수신했다.
  - 이어서 `1/pico/노원1관정/pump_state {"pump":"on|off","result":"applied"}` 응답을 확인했다.
- 브라우저 자동화 검증:
  - `aaa / 1111` 로그인 후 REGION1 팬 버튼 클릭 시 실제로 `pump_cmd`가 발행되는 것을 확인했다.
- REPL 복구:
  - Pico가 `>>>` 상태에 있을 때 `Ctrl-D` soft reboot로 정상 앱 런타임을 다시 올렸다.
  - 복구 후 로그:
    - `Wi-Fi connected: ('192.168.0.100', ...)`
    - `MQTT connected: broker=35.172.255.228 region=노원1관정`

### 31.6 현재 운영 기준
- 현재는 다음 경로가 정상이다.
  - 대시보드 팬 클릭
  - `pump_cmd` 발행
  - Pico 수신
  - `pump_state applied` 응답
  - DGUS `PUMP_ICON` 반영
- 다만 보드가 REPL 상태로 빠지면 동일 증상이 다시 나타날 수 있으므로, 증상 재발 시 먼저 보드가 `>>>` 상태인지 확인하는 것이 우선이다.

### 31.7 관련 파일
- `gswater_python/gswater_python/app.py`
- `code/2025123003_nodered.json`

### 31.8 검증 메모
- 최종 확인 시 `pump=on` 상태를 유지한 채로 보드를 남겨 두었다.
- 사용자는 물리 DGUS 디스플레이에서 팬 아이콘 회전 여부를 최종 확인하면 된다.


## 32. 2026-04-07 폴더 재구성 및 fast/slow / 문자발송 상태 점검

### 32.1 폴더 재구성 결과
- 운영 파일을 다음 구조로 재정리했다.
  - `node/`
    - 실제 Node-RED 운영 파일
  - `pico/`
    - 실제 Pico 운영 코드
  - `etc/`
    - 문서, 참조 자료, 이미지, 백업
  - `xfile/`
    - 미사용/임시/백업성 파일
- 루트에는 기존 동작 호환을 위해 심볼릭 링크를 남겼다.
  - `.node-red-user -> node/.node-red-user`
  - `.node-red-runtime -> node/.node-red-runtime`
  - `code -> node/code`
  - `gswater_python -> pico/gswater_python`
  - `agent.md -> etc/docs/agent.md`
  - `gswater_python_add -> etc/reference/gswater_python_add`
  - `gswater_python_add1 -> etc/reference/gswater_python_add1`
  - `image -> etc/image`
- 실제 운영 파일 경로는 다음이 canonical 기준이다.
  - `node/code/2025123003_nodered.json`
  - `node/.node-red-user/settings.js`
  - `node/.node-red-user/user_credentials.json`
  - `node/.node-red-user/solapi-config.local.json`
  - `pico/gswater_python/gswater_python/*`

### 32.2 경로 보정
- Node-RED 플로우 안에 하드코딩된 절대경로를 새 구조 기준으로 수정했다.
  - `user_credentials.json`
    - 기존: `/Users/mac/Desktop/gswatre_project/nodered/.node-red-user/user_credentials.json`
    - 변경: `/Users/mac/Desktop/gswatre_project/nodered/node/.node-red-user/user_credentials.json`
  - `solapi-config.local.json`
    - 기존: `/Users/mac/Desktop/gswatre_project/nodered/.node-red-user/solapi-config.local.json`
    - 변경: `/Users/mac/Desktop/gswatre_project/nodered/node/.node-red-user/solapi-config.local.json`
- 수정 대상:
  - `node/code/2025123003_nodered.json`
  - `node/.node-red-user/flows.json`

### 32.3 Node-RED 재기동 기준
- Node-RED는 새 구조 기준으로 다음 형태로 정상 기동을 확인했다.
  - `userDir`: `node/.node-red-user`
  - `settings`: `node/.node-red-user/settings.js`
  - `flows`: `node/code/2025123003_nodered.json`
- 확인 로그:
  - `Settings file  : /Users/mac/Desktop/gswatre_project/nodered/node/.node-red-user/settings.js`
  - `User directory : /Users/mac/Desktop/gswatre_project/nodered/node/.node-red-user`
  - `Flows file     : /Users/mac/Desktop/gswatre_project/nodered/node/code/2025123003_nodered.json`

### 32.4 HTTP / 로그인 검증
- HTTP 응답:
  - `/` `200`
  - `/ui/` `200`
- Playwright 기준 로그인 화면 확인:
  - `title = Login`
  - `loginVisible = true`
  - `setupVisible = false`

### 32.5 fast payload 현재 상태
- 외부 MQTT 브로커에서 `1/pico/노원1관정/dashboard_state` 실수신을 다시 확인했다.
- 현재 fast payload 예시:
  - `timestamp`
  - `data.water_level_pct = 8`
  - `data.well_depth_m = 61`
  - `data.solar = "on"`
  - `data.flow_ton = 0`
  - `data.battery_pct = 95`
  - `data.current_a = 0`
- 즉, fast payload는 폴더 재구성 이후에도 기존 동작대로 정상 송신/수신되고 있다.

### 32.6 slow payload 현재 상태
- 짧은 구독 창에서는 `dashboard_meta`를 새로 1건 더 잡지는 못했다.
- 다만 Node-RED 컨텍스트 저장소에서 slow 값이 정상 병합되어 있는 것을 확인했다.
- 현재 `display_cards_store_v2 -> REGION1 -> 1|노원1관정 -> data`에 존재하는 slow 계열 값:
  - `well_address = "문경시 충무로21"`
  - `horse_power = "34"`
  - `phone_numbers = ["010-5664-8540", "010-9397-8621", "010-9786-0000"]`
  - `network = "on"`
  - `version_text = "V7.0P1"`
  - `relay3_alarm_reason = "LOW"`
  - `stop_pct = 90`
  - `run_pct = 30`
  - `relay3_alarm = true`
  - `battery_stage = 3`
  - `pump = "on"`
  - `current_date = "2026-04-07"`
  - `pressure_enabled = true`
  - `alarm_pct = 20`
  - `well_level_text = " 61M"`
  - `channel = 7`
  - `motor_install_date = "2026-05-12"`
  - `lte = "on"`
  - `well_level_lockout = false`
- 즉, slow payload도 실제 운영 상태 기준으로 유지되고 있다.

### 32.7 문자발송 상태 점검
- 문자 발송 메타 저장은 정상이다.
  - `sms_alert_meta_by_well["노원1관정"]`
    - `wellName = "노원1관정"`
    - `wellAddress = "문경시 충무로21"`
    - `phoneNumbers = ["01056648540", "01093978621", "01097860000"]`
    - `alarmPct = 20`
- 문자 상태 저장도 정상이다.
  - `sms_alert_state_by_well["노원1관정"]["LOW"]`
    - `active = true`
    - `lastSentAt = 1775455161696`
  - `sms_alert_state_by_well["노원1관정"]["WELL"]`
    - `active = false`
- 따라서 현재 기준으로는 문자발송 로직이 정상 상태를 유지 중이다.

### 32.8 현재 판단
- fast payload:
  - 정상
- slow payload:
  - 정상 유지 중
- 문자발송:
  - 설정/상태 저장 정상
- 폴더 재구성 후에도 기존 UI와 핵심 동작은 유지된다.

### 32.9 관련 파일
- `node/code/2025123003_nodered.json`
- `node/.node-red-user/flows.json`
- `node/.node-red-user/settings.js`
- `node/.node-red-user/user_credentials.json`
- `node/.node-red-user/solapi-config.local.json`
- `node/.node-red-user/context/73a3c4ea7bfb6ad2/flow.json`
- `pico/gswater_python/gswater_python/app.py`
- `pico/gswater_python/gswater_python/mqtt_bridge_pico.py`

## 33. 2026-04-07 로그인 직후 slow 메타 즉시 복원 보강

### 33.1 문제 현상
- 로그인 후 REGION 카드가 바로 뜨더라도 slow 메타가 즉시 반영되지 않는 상태가 있었다.
- 실제 카드에서 보인 기본값:
  - `CH00`
  - `V0.0`
  - `정지/가동/알람 = 0`
  - `모터설치 ---- 년 -- 월 -- 일`
- fast payload는 정상 수신되고 있었으므로, 문제는 `dashboard_meta` 복원 경로였다.

### 33.2 원인 정리
- `dashboard_state`는 약 5초 주기로 계속 오지만, `dashboard_meta`는 `초기 1회 / 변경 시 / 1시간 주기` 구조라 로그인 직후 즉시 새 메시지가 오지 않을 수 있었다.
- Node-RED 카드 저장소에는 fast 값만 갱신되고, 마지막 slow 메타를 카드 재구성에 강제로 다시 병합하는 경로가 부족했다.
- Pico의 `dashboard_meta`는 retain 발행이 아니어서, 새 구독자 입장에서는 마지막 slow 메타를 즉시 받지 못했다.

### 33.3 적용한 최선안
- 사용자 승인 기준대로 `1 + 2`를 같이 적용했다.

1. Pico `dashboard_meta` retain 발행
- 파일:
  - `pico/gswater_python/gswater_python/mqtt_bridge_pico.py`
- 반영 내용:
  - `_publish_json(..., retain=False)` 형태로 확장
  - `dashboard_meta` 발행만 `retain=True` 적용

2. Node-RED slow 메타 캐시 보강
- 파일:
  - `node/code/2025123003_nodered.json`
- 반영 내용:
  - `dashboard_meta_cache_by_region` 저장소 추가
  - `dashboard_meta` 수신 시 `region_code` 기준과 `region_code-device_code` 기준으로 slow 메타 캐시 저장
  - 카드 재구성 시
    - `well_contact_directory`
    - `dashboard_meta_cache_by_region`
    - 기존 카드 데이터
    - 최신 수신 데이터
    순서로 병합되도록 조정

### 33.4 검증 결과
- Pico 보드 파일 확인:
  - `_publish_json(..., retain=False)` 존재
  - `self.client.publish(topic, body, retain=retain)` 존재
  - `dashboard_meta` 발행에 `retain=True` 적용 확인
- 외부 MQTT 브로커 신규 구독 확인:
  - 토픽: `1/pico/노원1관정/dashboard_meta`
  - 결과: `RETAIN = True`
- 신규 구독에서 즉시 받은 `dashboard_meta` 안에 아래 값들이 포함됨:
  - `channel = 7`
  - `version_text = "V7.0P1"`
  - `motor_install_date = "2026-05-12"`
  - `well_address = "문경시 충무로21"`
  - `horse_power = "34"`
  - `phone_numbers = ["010-5664-8540", "010-9397-8621", "010-9786-0000"]`
- Node-RED 컨텍스트 카드 저장소 확인:
  - `display_cards_store_v2 -> REGION1 -> 1|노원1관정 -> data`
  - 현재 병합 완료 필드:
    - `channel = 7`
    - `version_text = "V7.0P1"`
    - `motor_install_date = "2026-05-12"`
    - `alarm_pct = 20`
    - `run_pct = 30`
    - `stop_pct = 90`
    - `well_level_text = " 61M"`
    - `well_depth_m = 61`
    - `water_level_pct = 8`

### 33.5 현재 동작 기준
- 로그인 직후에도 카드가 마지막 slow 메타 기준으로 즉시 복원되어야 한다.
- 외부 MQTT 브로커의 retain `dashboard_meta`와 Node-RED 내부 캐시가 동시에 안전장치 역할을 한다.
- UI 구조는 변경하지 않았고, fast/slow 구조도 그대로 유지했다.

### 33.6 관련 파일
- `pico/gswater_python/gswater_python/mqtt_bridge_pico.py`
- `node/code/2025123003_nodered.json`
- `node/.node-red-user/context/73a3c4ea7bfb6ad2/flow.json`
