# EC2 Deployment

이 프로젝트는 `EC2 + Nginx + systemd + FastAPI + Next.js` 기준으로 배포하는 구성을 전제로 정리했습니다.

## 1. 서버 준비

Ubuntu 서버에서 패키지를 설치합니다.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx
```

Node 버전이 낮으면 `nvm` 또는 NodeSource로 `Node 20+`를 설치하는 편이 안전합니다.

## 2. 코드 업로드

로컬에서 EC2로 프로젝트를 복사합니다.

```bash
scp -i ~/Downloads/YOUR_KEY.pem -r /Users/YOUR_LOCAL_USER/shopping-agent-mvp ubuntu@YOUR_EC2_IP:/home/ubuntu/
```

## 3. 백엔드 설정

```bash
cd /home/ubuntu/shopping-agent-mvp/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

`backend/.env.local`을 운영 값으로 수정합니다.

예시:

```env
CHATKU_API_KEY=your_chatku_api_key
CHATKU_BASE_URL=https://factchat-cloud.mindlogic.ai/v1/gateway
CHATKU_MODEL=gpt-5.4
CHATKU_MODEL_PLANNER=gpt-5.4
CHATKU_MODEL_EXTRACTOR=gpt-5.4-mini
CHATKU_MODEL_FOLLOWUP=gpt-5.4-mini
CHATKU_MODEL_SUMMARY=gpt-5.4-nano

NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

DATABASE_URL=postgresql+psycopg://shopping_user:shopping_password@YOUR_DB_HOST:5432/shopping_agent
FRONTEND_ORIGIN=http://YOUR_DOMAIN_OR_EC2_IP
```

## 4. 프론트 설정

```bash
cd /home/ubuntu/shopping-agent-mvp/frontend
npm install
npm run build
```

`frontend/.env.local` 예시:

```env
NEXT_PUBLIC_API_BASE_URL=http://YOUR_DOMAIN_OR_EC2_IP
```

도메인과 HTTPS를 붙이면 `https://YOUR_DOMAIN`으로 바꾸는 게 맞습니다.

## 5. systemd 등록

서비스 파일을 서버에 복사합니다.

```bash
sudo cp /home/ubuntu/shopping-agent-mvp/deploy/ec2/shopping-agent-backend.service /etc/systemd/system/
sudo cp /home/ubuntu/shopping-agent-mvp/deploy/ec2/shopping-agent-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable shopping-agent-backend
sudo systemctl enable shopping-agent-frontend
sudo systemctl start shopping-agent-backend
sudo systemctl start shopping-agent-frontend
```

상태 확인:

```bash
sudo systemctl status shopping-agent-backend
sudo systemctl status shopping-agent-frontend
```

로그 확인:

```bash
journalctl -u shopping-agent-backend -f
journalctl -u shopping-agent-frontend -f
```

## 6. Nginx 연결

```bash
sudo cp /home/ubuntu/shopping-agent-mvp/deploy/ec2/nginx.shopping-ai-agent.conf /etc/nginx/sites-available/shopping-agent
sudo ln -s /etc/nginx/sites-available/shopping-agent /etc/nginx/sites-enabled/shopping-agent
sudo nginx -t
sudo systemctl restart nginx
```

`YOUR_DOMAIN_OR_EC2_IP`는 실제 도메인 또는 EC2 퍼블릭 IP로 바꿔야 합니다.

## 7. HTTPS

도메인이 연결된 상태라면:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

## 8. 보안 그룹

최소한 다음 포트만 엽니다.

- `22` SSH
- `80` HTTP
- `443` HTTPS

`3000`, `8000`, `5432`는 외부에 직접 열지 않는 편이 안전합니다.

## 9. 추천 운영 구성

- DB는 `SQLite` 대신 `PostgreSQL` 또는 `RDS PostgreSQL`
- 운영에서는 `backend/run.py`의 `reload=True`를 쓰지 않음
- 프론트는 `npm run build` 후 `next start`
- `.env.local`은 Git에 올리지 않음
