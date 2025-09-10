// API 서비스 레이어
const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8001';
const RANKING_API_BASE_URL = process.env.VITE_RANKING_API_BASE_URL || 'http://localhost:8002';

class ApiService {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.rankingBaseURL = RANKING_API_BASE_URL;
  }

  // 기본 HTTP 요청 메서드
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': this.generateCorrelationId(),
      },
    };

    const config = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error?.message || 'API 요청 실패');
      }
      
      return data;
    } catch (error) {
      console.error('API 요청 실패:', error);
      
      // 마이크로서비스가 실행되지 않을 때 Mock 데이터 반환
      if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
        console.warn('마이크로서비스가 실행되지 않음. Mock 데이터를 사용합니다.');
        return this.getMockData(endpoint);
      }
      
      throw error;
    }
  }

  // 랭킹 서비스 전용 요청 메서드
  async rankingRequest(endpoint, options = {}) {
    const url = `${this.rankingBaseURL}${endpoint}`;
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
        'X-Correlation-ID': this.generateCorrelationId(),
      },
    };

    const config = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error?.message || '랭킹 API 요청 실패');
      }
      
      return data;
    } catch (error) {
      console.error('랭킹 API 요청 실패:', error);
      
      // 랭킹 서비스가 실행되지 않을 때 Mock 데이터 반환
      if (error.message.includes('Failed to fetch') || error.message.includes('ERR_CONNECTION_REFUSED')) {
        console.warn('랭킹 서비스가 실행되지 않음. Mock 데이터를 사용합니다.');
        return this.getRankingMockData(endpoint);
      }
      
      throw error;
    }
  }

  // 상관관계 ID 생성
  generateCorrelationId() {
    return Math.random().toString(36).substring(2, 15) + 
           Math.random().toString(36).substring(2, 15);
  }

  // Mock 데이터 반환 (마이크로서비스가 실행되지 않을 때)
  getMockData(endpoint) {
    if (endpoint.includes('/currencies/latest')) {
      return {
        success: true,
        data: {
          base: 'KRW',
          rates: {
            'USD': 1350.50,
            'JPY': 9.25,
            'EUR': 1480.75,
            'GBP': 1720.30,
            'CNY': 190.45
          },
          timestamp: new Date().toISOString(),
          cache_hit: false
        }
      };
    }
    
    if (endpoint.includes('/price-index')) {
      return {
        success: true,
        data: {
          country_code: 'US',
          big_mac_index: 5.81,
          starbucks_index: 4.45,
          timestamp: new Date().toISOString()
        }
      };
    }
    
    if (endpoint.includes('/health')) {
      return {
        success: true,
        data: {
          status: 'healthy',
          service: 'currency-service-mock',
          version: '1.0.0-mock'
        }
      };
    }
    
    // 기본 Mock 응답
    return {
      success: true,
      data: { message: 'Mock data - 서비스가 실행되지 않음' }
    };
  }

  // 랭킹 서비스 Mock 데이터 반환
  getRankingMockData(endpoint) {
    if (endpoint.includes('/rankings')) {
      return {
        success: true,
        data: {
          period: 'daily',
          total_selections: 1250,
          last_updated: new Date().toISOString(),
          ranking: [
            { country_code: 'JP', country_name: '일본', selection_count: 245, rank: 1 },
            { country_code: 'US', country_name: '미국', selection_count: 198, rank: 2 },
            { country_code: 'TH', country_name: '태국', selection_count: 156, rank: 3 },
            { country_code: 'VN', country_name: '베트남', selection_count: 134, rank: 4 },
            { country_code: 'SG', country_name: '싱가포르', selection_count: 98, rank: 5 },
            { country_code: 'CN', country_name: '중국', selection_count: 87, rank: 6 },
            { country_code: 'GB', country_name: '영국', selection_count: 76, rank: 7 },
            { country_code: 'AU', country_name: '호주', selection_count: 65, rank: 8 },
            { country_code: 'CA', country_name: '캐나다', selection_count: 54, rank: 9 },
            { country_code: 'DE', country_name: '독일', selection_count: 43, rank: 10 }
          ]
        }
      };
    }
    
    // 기본 랭킹 Mock 응답
    return {
      success: true,
      data: { message: 'Mock ranking data - 랭킹 서비스가 실행되지 않음' }
    };
  }

  // 환율 조회
  async getExchangeRates(symbols = 'USD,JPY,EUR,GBP,CNY', base = 'KRW') {
    const symbolsParam = Array.isArray(symbols) ? symbols.join(',') : symbols;
    return this.request(`/api/v1/currencies/latest?symbols=${symbolsParam}&base=${base}`);
  }

  // 물가 지수 조회
  async getPriceIndex(country, baseCountry = 'KR') {
    return this.request(`/api/v1/price-index?country=${country}&base_country=${baseCountry}`);
  }

  // 통화 정보 조회
  async getCurrencyInfo(currencyCode) {
    return this.request(`/api/v1/currencies/${currencyCode}`);
  }

  // 헬스 체크
  async healthCheck() {
    return this.request('/health');
  }

  // 랭킹 서비스 API 메서드들
  
  // 랭킹 조회
  async getRankings(period = 'daily', limit = 10, offset = 0) {
    return this.rankingRequest(`/api/v1/rankings?period=${period}&limit=${limit}&offset=${offset}`);
  }

  // 사용자 선택 기록
  async recordSelection(selectionData) {
    return this.rankingRequest('/api/v1/rankings/selections', {
      method: 'POST',
      body: JSON.stringify(selectionData)
    });
  }

  // 국가별 통계 조회
  async getCountryStats(countryCode, period = '7d') {
    return this.rankingRequest(`/api/v1/rankings/stats/${countryCode}?period=${period}`);
  }

  // 랭킹 계산 트리거 (관리자용)
  async triggerRankingCalculation(period) {
    return this.rankingRequest(`/api/v1/rankings/calculate?period=${period}`, {
      method: 'POST'
    });
  }
}

// 싱글톤 인스턴스 생성
const apiService = new ApiService();

export default apiService;
