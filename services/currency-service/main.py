"""
Currency Service - 실시간 환율 조회 서비스
FastAPI 기반 웹 서버 (로컬 개발용)
AWS Lambda 배포 시에는 lambda_handler 함수 사용
"""
import os
import sys
from contextlib import asynccontextmanager

# 상위 디렉토리의 shared 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import List, Optional

from shared.config import init_config, get_config
from shared.database import init_database, get_db_manager
import logging
from shared.logging import set_correlation_id, set_request_id
from shared.models import (
    LatestRatesResponse, CurrencyInfo, PriceIndex, 
    CurrencyCode, CountryCode, SuccessResponse, ErrorResponse
)
from shared.exceptions import (
    BaseServiceException, InvalidCurrencyCodeError, 
    InvalidCountryCodeError, get_http_status_code
)
from shared.utils import SecurityUtils

from app.services.currency_provider import CurrencyProvider
from app.services.price_index_provider import PriceIndexProvider

# 로거 초기화
logger = logging.getLogger(__name__)

# 전역 변수
currency_provider: Optional[CurrencyProvider] = None
price_index_provider: Optional[PriceIndexProvider] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global currency_provider, price_index_provider
    
    try:
        # 설정 초기화
        config = init_config("currency-service")
        logger.info("Currency Service starting", version=config.service_version)
        
        # 데이터베이스 초기화
        await init_database()
        logger.info("Database connections initialized")
        
        # 서비스 프로바이더 초기화
        currency_provider = CurrencyProvider()
        price_index_provider = PriceIndexProvider()
        
        logger.info("Currency Service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start Currency Service", error=e)
        raise
    finally:
        # 정리 작업
        db_manager = get_db_manager()
        await db_manager.close()
        logger.info("Currency Service stopped")


# FastAPI 앱 생성
app = FastAPI(
    title="Currency Service",
    description="실시간 환율 조회 서비스",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 개발 서버 (기본 포트)
        "http://localhost:5174",  # Vite 개발 서버 (실제 실행 포트)
        "http://localhost:3000",  # React 개발 서버
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 정적 파일 서빙 설정
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 의존성 함수들
def get_currency_provider() -> CurrencyProvider:
    """Currency Provider 의존성"""
    if currency_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return currency_provider


def get_price_index_provider() -> PriceIndexProvider:
    """Price Index Provider 의존성"""
    if price_index_provider is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return price_index_provider


# 미들웨어
@app.middleware("http")
async def logging_middleware(request, call_next):
    """로깅 미들웨어"""
    # 상관관계 ID 설정
    correlation_id = request.headers.get("X-Correlation-ID") or SecurityUtils.generate_correlation_id()
    set_correlation_id(correlation_id)
    
    # 요청 ID 설정 (Lambda에서는 AWS Request ID 사용)
    request_id = request.headers.get("X-Request-ID") or SecurityUtils.generate_uuid()
    set_request_id(request_id)
    
    logger.info(f"Request started: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        
        logger.info(f"Request completed: {request.method} {request.url} - {response.status_code}")
        
        # 응답 헤더에 상관관계 ID 추가
        response.headers["X-Correlation-ID"] = correlation_id
        return response
        
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url} - {e}")
        raise


# 예외 처리기
@app.exception_handler(BaseServiceException)
async def service_exception_handler(request, exc: BaseServiceException):
    """서비스 예외 처리기"""
    logger.error(f"Service exception: {exc.error_code} - {exc.message}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=get_http_status_code(exc),
        content={
            "success": False,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "version": "v1",
            "error": exc.to_dict()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """일반 예외 처리기"""
    logger.error(f"Unexpected error occurred: {exc}")
    
    from datetime import datetime
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "version": "v1",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


# CORS OPTIONS 핸들러 추가
@app.options("/{path:path}")
async def options_handler(path: str):
    """CORS preflight 요청 처리"""
    return {"message": "OK"}

# API 엔드포인트들
@app.get("/health")
async def health_check():
    """헬스 체크"""
    return SuccessResponse(
        data={
            "status": "healthy",
            "service": "currency-service",
            "version": get_config().service_version
        }
    )


@app.get("/", response_class=HTMLResponse)
async def frontend_page():
    """프론트엔드 페이지"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>환율 및 물가 지수 조회</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 300;
            }
            
            .header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .content {
                padding: 30px;
            }
            
            .controls {
                display: flex;
                gap: 15px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                align-items: center;
            }
            
            .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 25px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }
            
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            
            .btn:active {
                transform: translateY(0);
            }
            
            .loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #666;
            }
            
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto 10px;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .data-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            }
            
            .data-table th {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 500;
                font-size: 14px;
            }
            
            .data-table td {
                padding: 15px;
                border-bottom: 1px solid #eee;
                font-size: 14px;
            }
            
            .data-table tr:hover {
                background-color: #f8f9ff;
            }
            
            .data-table tr:last-child td {
                border-bottom: none;
            }
            
            .currency-code {
                font-weight: bold;
                color: #667eea;
            }
            
            .rate {
                font-weight: 600;
                color: #2c3e50;
            }
            
            .price-index {
                color: #27ae60;
                font-weight: 500;
            }
            
            .error {
                background: #ffebee;
                color: #c62828;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #c62828;
            }
            
            .info {
                background: #e3f2fd;
                color: #1565c0;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #1565c0;
            }
            
            .timestamp {
                text-align: center;
                color: #666;
                font-size: 12px;
                margin-top: 20px;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 5px;
            }
            
            .graph-icon {
                width: 20px;
                height: 20px;
                background: #667eea;
                border-radius: 3px;
                display: inline-block;
                position: relative;
            }
            
            .graph-icon::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 8px;
                height: 8px;
                background: white;
                border-radius: 1px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 환율 및 물가 지수 조회</h1>
                <p>실시간 환율 정보와 빅맥/스타벅스 지수를 확인하세요</p>
            </div>
            
            <div class="content">
                <div class="controls">
                    <button class="btn" onclick="loadExchangeRates()">💱 환율 조회</button>
                    <button class="btn" onclick="loadPriceIndex()">🍔 물가 지수 조회</button>
                    <button class="btn" onclick="loadAllData()">📊 전체 데이터 조회</button>
                </div>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>데이터를 불러오는 중...</p>
                </div>
                
                <div id="error" class="error" style="display: none;"></div>
                <div id="info" class="info" style="display: none;"></div>
                
                <table class="data-table" id="dataTable" style="display: none;">
                    <thead>
                        <tr>
                            <th>국가명</th>
                            <th>통화</th>
                            <th>환율 (KRW)</th>
                            <th>빅맥 지수</th>
                            <th>스타벅스 지수</th>
                            <th>그래프</th>
                        </tr>
                    </thead>
                    <tbody id="dataTableBody">
                    </tbody>
                </table>
                
                <div class="timestamp" id="timestamp"></div>
            </div>
        </div>
        
        <script>
            const API_BASE = '/api/v1';
            
            function showLoading() {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('dataTable').style.display = 'none';
                document.getElementById('error').style.display = 'none';
                document.getElementById('info').style.display = 'none';
            }
            
            function hideLoading() {
                document.getElementById('loading').style.display = 'none';
            }
            
            function showError(message) {
                hideLoading();
                const errorDiv = document.getElementById('error');
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
            }
            
            function showInfo(message) {
                hideLoading();
                const infoDiv = document.getElementById('info');
                infoDiv.textContent = message;
                infoDiv.style.display = 'block';
            }
            
            function updateTimestamp() {
                const now = new Date();
                document.getElementById('timestamp').textContent = 
                    `마지막 업데이트: ${now.toLocaleString('ko-KR')}`;
            }
            
            async function loadExchangeRates() {
                showLoading();
                try {
                    const response = await fetch(`${API_BASE}/currencies/latest?symbols=USD,JPY,EUR,GBP,CNY`);
                    const data = await response.json();
                    
                    if (data.success) {
                        displayExchangeRates(data.data);
                    } else {
                        showError('환율 데이터를 불러오는데 실패했습니다.');
                    }
                } catch (error) {
                    showError('서버 연결에 실패했습니다: ' + error.message);
                }
            }
            
            async function loadPriceIndex() {
                showLoading();
                try {
                    // 여러 국가의 물가 지수를 조회
                    const countries = ['US', 'JP', 'GB', 'CN'];
                    const promises = countries.map(country => 
                        fetch(`${API_BASE}/price-index?country=${country}`)
                            .then(res => res.json())
                    );
                    
                    const results = await Promise.all(promises);
                    const validResults = results.filter(result => result.success);
                    
                    if (validResults.length > 0) {
                        displayPriceIndex(validResults);
                    } else {
                        showError('물가 지수 데이터를 불러오는데 실패했습니다.');
                    }
                } catch (error) {
                    showError('서버 연결에 실패했습니다: ' + error.message);
                }
            }
            
            async function loadAllData() {
                showLoading();
                try {
                    // 환율과 물가 지수를 동시에 조회
                    const [ratesResponse, ...priceResponses] = await Promise.all([
                        fetch(`${API_BASE}/currencies/latest?symbols=USD,JPY,EUR,GBP,CNY`),
                        fetch(`${API_BASE}/price-index?country=US`),
                        fetch(`${API_BASE}/price-index?country=JP`),
                        fetch(`${API_BASE}/price-index?country=GB`),
                        fetch(`${API_BASE}/price-index?country=CN`)
                    ]);
                    
                    const ratesData = await ratesResponse.json();
                    const priceData = await Promise.all(priceResponses.map(res => res.json()));
                    
                    if (ratesData.success) {
                        displayAllData(ratesData.data, priceData.filter(p => p.success));
                    } else {
                        showError('데이터를 불러오는데 실패했습니다.');
                    }
                } catch (error) {
                    showError('서버 연결에 실패했습니다: ' + error.message);
                }
            }
            
            function displayExchangeRates(data) {
                hideLoading();
                const tbody = document.getElementById('dataTableBody');
                tbody.innerHTML = '';
                
                const countryMap = {
                    'USD': { name: '미국', code: 'US' },
                    'JPY': { name: '일본', code: 'JP' },
                    'EUR': { name: '유럽', code: 'EU' },
                    'GBP': { name: '영국', code: 'GB' },
                    'CNY': { name: '중국', code: 'CN' }
                };
                
                Object.entries(data.rates).forEach(([currency, rate]) => {
                    const country = countryMap[currency] || { name: currency, code: currency };
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${country.name}</td>
                        <td><span class="currency-code">${currency}</span></td>
                        <td><span class="rate">${rate.toLocaleString()}원</span></td>
                        <td>-</td>
                        <td>-</td>
                        <td><div class="graph-icon"></div></td>
                    `;
                });
                
                document.getElementById('dataTable').style.display = 'table';
                updateTimestamp();
                showInfo(`환율 데이터를 성공적으로 불러왔습니다. (캐시: ${data.cache_hit ? '적중' : '미적중'})`);
            }
            
            function displayPriceIndex(data) {
                hideLoading();
                const tbody = document.getElementById('dataTableBody');
                tbody.innerHTML = '';
                
                const countryMap = {
                    'US': { name: '미국', currency: 'USD' },
                    'JP': { name: '일본', currency: 'JPY' },
                    'GB': { name: '영국', currency: 'GBP' },
                    'CN': { name: '중국', currency: 'CNY' }
                };
                
                data.forEach(item => {
                    const country = countryMap[item.data.country_code] || { name: item.data.country_code, currency: item.data.country_code };
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${country.name}</td>
                        <td><span class="currency-code">${country.currency}</span></td>
                        <td>-</td>
                        <td><span class="price-index">$${item.data.big_mac_index || 'N/A'}</span></td>
                        <td><span class="price-index">$${item.data.starbucks_index || 'N/A'}</span></td>
                        <td><div class="graph-icon"></div></td>
                    `;
                });
                
                document.getElementById('dataTable').style.display = 'table';
                updateTimestamp();
                showInfo('물가 지수 데이터를 성공적으로 불러왔습니다.');
            }
            
            function displayAllData(ratesData, priceData) {
                hideLoading();
                const tbody = document.getElementById('dataTableBody');
                tbody.innerHTML = '';
                
                const countryMap = {
                    'USD': { name: '미국', code: 'US' },
                    'JPY': { name: '일본', code: 'JP' },
                    'EUR': { name: '유럽', code: 'EU' },
                    'GBP': { name: '영국', code: 'GB' },
                    'CNY': { name: '중국', code: 'CN' }
                };
                
                // 환율 데이터를 기준으로 테이블 생성
                Object.entries(ratesData.rates).forEach(([currency, rate]) => {
                    const country = countryMap[currency] || { name: currency, code: currency };
                    
                    // 해당 국가의 물가 지수 찾기
                    const priceInfo = priceData.find(p => p.data.country_code === country.code);
                    
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${country.name}</td>
                        <td><span class="currency-code">${currency}</span></td>
                        <td><span class="rate">${rate.toLocaleString()}원</span></td>
                        <td><span class="price-index">$${priceInfo ? (priceInfo.data.big_mac_index || 'N/A') : 'N/A'}</span></td>
                        <td><span class="price-index">$${priceInfo ? (priceInfo.data.starbucks_index || 'N/A') : 'N/A'}</span></td>
                        <td><div class="graph-icon"></div></td>
                    `;
                });
                
                document.getElementById('dataTable').style.display = 'table';
                updateTimestamp();
                showInfo(`전체 데이터를 성공적으로 불러왔습니다. (환율 캐시: ${ratesData.cache_hit ? '적중' : '미적중'})`);
            }
            
            // 페이지 로드 시 자동으로 환율 데이터 로드
            window.addEventListener('load', () => {
                loadExchangeRates();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/v1/currencies/latest", response_model=LatestRatesResponse)
async def get_latest_rates(
    symbols: Optional[str] = Query(None, description="쉼표로 구분된 통화 코드"),
    base: str = Query("KRW", description="기준 통화 코드"),
    provider: CurrencyProvider = Depends(get_currency_provider)
):
    """
    최신 환율 정보 조회
    
    - **symbols**: 조회할 통화 코드들 (예: USD,JPY,EUR)
    - **base**: 기준 통화 코드 (기본값: KRW)
    """
    try:
        # 파라미터 파싱
        currency_codes = []
        if symbols:
            currency_codes = [code.strip().upper() for code in symbols.split(",")]
            # 통화 코드 검증
            for code in currency_codes:
                if code not in [c.value for c in CurrencyCode]:
                    raise InvalidCurrencyCodeError(code)
        
        # 기준 통화 검증
        if base.upper() not in [c.value for c in CurrencyCode]:
            raise InvalidCurrencyCodeError(base)
        
        # 환율 데이터 조회
        rates_data = await provider.get_latest_rates(currency_codes, base.upper())
        
        return LatestRatesResponse(data=rates_data)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest rates: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exchange rates")


@app.get("/api/v1/price-index", response_model=SuccessResponse)
async def get_price_index(
    country: str = Query(..., description="국가 코드"),
    base_country: str = Query("KR", description="기준 국가 코드"),
    provider: PriceIndexProvider = Depends(get_price_index_provider)
):
    """
    물가 지수 조회

    - **country**: 대상 국가 코드 (예: JP)
    - **base_country**: 기준 국가 코드 (기본값: KR)
    """
    # TODO: 실시간 서비스 변경 - /api/v1/price-index 경로로 변경하여 {currency_code} 라우트 충돌 방지
    # - CountryCode enum에 추가 국가 지원
    # - 실제 물가 데이터로 계산 (빅맥/스타벅스 API 연동)
    try:
        # 국가 코드 검증
        country = country.upper()
        base_country = base_country.upper()
        
        if country not in [c.value for c in CountryCode]:
            raise InvalidCountryCodeError(country)
        if base_country not in [c.value for c in CountryCode]:
            raise InvalidCountryCodeError(base_country)
        
        # 물가 지수 조회
        price_index = await provider.get_price_index(country, base_country)
        
        return SuccessResponse(data=price_index)
        
    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get price index for {country}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve price index")


@app.get("/api/v1/currencies/{currency_code}", response_model=SuccessResponse)
async def get_currency_info(
    currency_code: str,
    country: Optional[str] = Query(None, description="국가 코드 (price-index 전용)"),
    base_country: str = Query("KR", description="기준 국가 코드 (price-index 전용)"),
    currency_provider: CurrencyProvider = Depends(get_currency_provider),
    price_provider: PriceIndexProvider = Depends(get_price_index_provider)
):
    """
    통화별 상세 정보 조회 또는 물가 지수 조회

    - **currency_code**: 3자리 통화 코드 (예: USD) 또는 "price-index"
    - **country**: 물가 지수 조회 시 대상 국가 코드 (예: JP)
    - **base_country**: 물가 지수 조회 시 기준 국가 코드 (기본값: KR)
    """
    try:
        # 통화 코드 검증
        currency_code = currency_code.upper()

        # price-index 특별 처리
        if currency_code == "PRICE-INDEX":
            if not country:
                raise HTTPException(status_code=400, detail="country parameter is required for price-index")

            # 국가 코드 검증
            country = country.upper()
            base_country = base_country.upper()

            if country not in [c.value for c in CountryCode]:
                raise InvalidCountryCodeError(country)
            if base_country not in [c.value for c in CountryCode]:
                raise InvalidCountryCodeError(base_country)

            # 물가 지수 조회
            price_index = await price_provider.get_price_index(country, base_country)
            return SuccessResponse(data=price_index)

        # 일반 통화 정보 조회
        if currency_code not in [c.value for c in CurrencyCode]:
            raise InvalidCurrencyCodeError(currency_code)

        # 통화 정보 조회
        currency_info = await currency_provider.get_currency_info(currency_code)

        return SuccessResponse(data=currency_info)

    except BaseServiceException:
        raise
    except Exception as e:
        logger.error(f"Failed to get info for {currency_code}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve information")


# AWS Lambda 핸들러 (배포 시 사용)
def lambda_handler(event, context):
    """
    AWS Lambda 핸들러
    
    AWS 배포 시 수정 필요사항:
    1. Mangum 설치: pip install mangum
    2. 아래 코드 주석 해제 및 수정
    3. Lambda 환경변수 설정
    4. VPC 설정 (Aurora, ElastiCache 접근용)
    5. IAM 역할 권한 설정
    """
    # TODO: AWS 배포 시 아래 코드 활성화
    # from mangum import Mangum
    # handler = Mangum(app, lifespan="off")
    # return handler(event, context)
    pass


# 로컬 개발 서버 실행
if __name__ == "__main__":
    # 환경 변수에서 설정 로드
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))  # Currency Service는 8001 포트
    
    logger.info(f"Starting Currency Service on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,  # 개발 모드에서만 사용
        log_level="info"
    )