# OCI ARM Auto Launcher

Oracle Cloud Free Tier ARM 인스턴스 `VM.Standard.A1.Flex` 생성을 반복 시도하는 프로그램입니다.

- **여러 계정을 동시에** 시도할 수 있습니다 (한 사이클에 계정1 → 계정2 ... 순으로 시도, 성공한 계정은 제외하고 나머지는 다음 사이클에 재시도).
- 모든 설정을 **GUI 한 화면**에서 입력합니다. (`config.json` 한 파일에 저장)
- **Docker / Hyper-V / Python 설치 불필요** — 단일 실행 파일(`.exe`)로 동작합니다.

실행 방식:

- **A. GUI 실행 파일 (권장)** — `oci-arm-auto-gui.exe`
- **B. CLI 실행 파일** — `oci-arm-auto.exe` (백그라운드/서버용, 콘솔)
- **C. Docker** (선택, 부록 참고)

---

## A. GUI로 사용하기 (권장)

### 1. 다운로드

GitHub 저장소의 **Releases** 페이지에서 받습니다.

- `oci-arm-auto-portable.zip` — GUI(빠른 실행) + CLI 실행 파일 + 예시 설정이 모두 포함 **(권장)**
- `oci-arm-auto.exe` — CLI 실행 파일만 (백그라운드/서버용)

`oci-arm-auto-portable.zip`을 받아 원하는 폴더에 압축을 풉니다.

> GUI는 폴더형(`oci-arm-auto-gui.exe` + `_internal` 폴더)으로 제공됩니다.
> **`_internal` 폴더와 exe를 항상 같은 위치에 두세요.** (압축을 그대로 풀면 됩니다.)
> 이 방식이라 실행 파일이 **즉시 열립니다.**

### 2. 실행

`run.bat`을 더블클릭하거나 `oci-arm-auto-gui.exe`를 직접 실행합니다.
GUI 창이 열립니다.


### 3. 설정 입력

**전역 설정 (Global settings)**

| 항목 | 설명 |
|------|------|
| Retry interval (sec) | 재시도 간격. 기본 1800초(30분). 너무 짧으면 429 TooManyRequests에 걸릴 수 있음 |
| Max attempts | 최대 시도 사이클 수. `0`이면 성공할 때까지 무한 반복 |
| Discord webhook URL | (선택) 알림용 Discord 웹훅 |
| Discord user ID | (선택) 멘션할 사용자 ID |
| Notify on capacity | 켜면 재고 부족(capacity)도 Discord 알림 |

**계정 (Accounts)**

`+ Add account` 버튼으로 계정 탭을 추가하고, 각 탭에 아래 값을 입력합니다.
`- Remove current`로 현재 탭을 삭제합니다.

> **Account name**은 OCI와 무관한 **임의의 별명**입니다. 로그에 어느 계정인지 표시하는 용도이며, `main`·`회사계정` 등 아무 이름이나 넣으면 됩니다.

| 항목 | 어디서 얻나 |
|------|------|
| Region | 드롭다운에서 선택 (기본: `ap-chuncheon-1` 춘천) |
| User OCID | Profile → User settings → OCID |
| API key fingerprint | API Key 추가 시 표시되는 fingerprint |
| Tenancy OCID | Profile → Tenancy → OCID |
| Compartment OCID | 비워두면 Tenancy OCID를 사용 (루트 컴파트먼트) |
| Image OCID | 생성하려는 이미지의 OCID |
| Subnet OCID | 사용할 서브넷 OCID |
| Availability domain | 예: `EizN:AP-OSAKA-1-AD-1` |
| Instance display name | 인스턴스 이름 |
| Shape / OCPUs / Memory | 기본 `VM.Standard.A1.Flex`, 4 OCPU, 24GB (Free Tier 최대) |
| API private key (PEM) | OCI API 개인키 전체 내용. **`-----BEGIN PRIVATE KEY-----` 와 `-----END PRIVATE KEY-----` 줄까지 포함**해서 붙여넣기 |
| SSH public key | 인스턴스 접속용 **공개키** (`ssh-rsa ...` 또는 `ssh-ed25519 ...`) |

> 개인키/공개키 모두 **파일 경로가 아니라 내용을 직접 붙여넣습니다.** 별도 파일 관리가 필요 없습니다.

### 4. 저장하고 실행

1. **Save config** — 입력값을 `config.json`에 저장합니다. (실행 파일과 같은 폴더)
2. **Start** — 활성화된(Enabled) 계정들에 대해 인스턴스 생성을 반복 시도합니다.
3. 로그 창과 `logs/output.log`에 진행 상황이 실시간 기록됩니다.
4. **Stop** — 현재 사이클을 마치는 대로 중지합니다.


---

## B. CLI로 사용하기 (백그라운드/서버)

`oci-arm-auto.exe`(또는 `python create_instance.py`)는 같은 폴더의 `config.json`을 읽어 헤드리스로 실행합니다.

```bat
oci-arm-auto.exe
oci-arm-auto.exe --config "D:\path\to\config.json"
```

`config.json`이 없으면 템플릿이 자동 생성됩니다. GUI로 먼저 설정을 저장하는 것을 권장합니다.

---

## config.json 구조 (참고)

```jsonc
{
  "request_interval": 1800,
  "max_attempts": 0,
  "discord_webhook_url": "",
  "discord_user_id": "",
  "discord_notify_capacity": true,
  "accounts": [
    {
      "name": "account-1",
      "enabled": true,
      "region": "ap-osaka-1",
      "user_ocid": "...", "fingerprint": "...", "tenancy_ocid": "...",
      "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
      "compartment_ocid": "",
      "image_id": "...", "subnet_id": "...", "availability_domain": "...",
      "ssh_public_key": "ssh-rsa ...",
      "display_name": "big-arm-1", "shape": "VM.Standard.A1.Flex",
      "ocpus": 4, "memory_gb": 24,
      "boot_volume_gb": 150, "boot_volume_vpus_per_gb": 10,
      "assign_public_ip": true
    }
  ]
}
```

전체 예시는 `config.example.json`을 참고하세요.

> **보안 주의:** `config.json`에는 OCI API 개인키가 들어갑니다. 이 파일은 `.gitignore`에 등록되어 있어 저장소에 커밋되지 않습니다. 공유하지 마세요.


---

## 직접 빌드하기

### GitHub Actions로 빌드 + Release 업로드

`.github/workflows/build-release.yml`가 Windows 러너에서 GUI/CLI exe와 portable zip을 빌드해 Release에 올립니다.

- **태그 푸시**: `v1.0.0` 같은 태그를 푸시하면 해당 태그의 Release가 생성됩니다.

  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```

- **수동 실행**: GitHub **Actions** 탭 → "Build and Release" → **Run workflow** (필요 시 `tag` 입력)

### 로컬(Windows)에서 빌드

```powershell
.\build.ps1
```

`dist\oci-arm-auto-gui\`(GUI 폴더, 빠른 실행)와 `dist\oci-arm-auto.exe`(CLI)가 생성됩니다.

---

## 부록 C. Docker로 사용하기 (선택)

```powershell
.\setup.ps1     # config.example.json -> config.json 복사
# config.json 값 입력 후
.\start.ps1     # docker compose up -d --build
.\logs.ps1      # docker compose logs -f
.\stop.ps1      # docker compose down
```

Docker는 `config.json`을 컨테이너에 마운트해 CLI 러너를 실행합니다. (GUI는 사용하지 않음)

---

## 자주 나는 오류

- **Out of host capacity** — ARM 재고 부족입니다. 정상적인 실패이며 시간이 지나면 재시도합니다.
- **SSH public key looks like a private key** — SSH 칸에 개인키를 넣은 경우입니다. `ssh-rsa ...` / `ssh-ed25519 ...` 형식의 공개키를 넣으세요.
- **401 / NotAuthenticated** — User OCID, fingerprint, tenancy, region, 개인키 내용을 확인하세요.
- **404 / NotAuthorizedOrNotFound** — Image / Subnet / Tenancy / Availability domain / region이 서로 맞는지 확인하세요.
