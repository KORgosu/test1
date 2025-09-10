import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import styled from 'styled-components';
import ExchangeRateChart from '../components/country/ExchangeRateChart';
import CountryCard from '../components/country/CountryCard';
import useCurrencyData from '../hooks/useCurrencyData';

const ComparisonContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  background: white;
  min-height: 100vh;
`;

const PageTitle = styled.h1`
  color: #2c3e50;
  margin-bottom: 2rem;
  text-align: center;
`;

const ChartSection = styled.section`
  background: white;
  padding: 2rem;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  margin-bottom: 2rem;
`;

const SectionTitle = styled.h2`
  color: #2c3e50;
  margin-bottom: 1.5rem;
`;

const CountriesGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
`;

const BackButton = styled.button`
  background-color: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  cursor: pointer;
  margin-bottom: 2rem;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: #5a6fd8;
  }
`;

const NoCountriesMessage = styled.div`
  text-align: center;
  padding: 3rem;
  color: #666;
  font-size: 1.1rem;
`;

const RefreshButton = styled.button`
  background-color: #28a745;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  cursor: pointer;
  margin-left: 1rem;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: #218838;
  }
  
  &:disabled {
    background-color: #6c757d;
    cursor: not-allowed;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
`;

const ComparisonPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [selectedCountries, setSelectedCountries] = useState([]);
  const { fetchAllData, loading } = useCurrencyData();

  useEffect(() => {
    const countriesParam = searchParams.get('countries');
    if (countriesParam) {
      const countries = countriesParam.split(',').filter(country => country.trim());
      setSelectedCountries(countries);
    } else {
      // URL 파라미터가 없으면 기본 국가들로 설정
      setSelectedCountries(['US', 'JP', 'GB', 'CN']);
    }
  }, [searchParams]);

  const handleBackToHome = () => {
    navigate('/');
  };

  const handleRefreshData = async () => {
    try {
      await fetchAllData();
    } catch (error) {
      console.error('데이터 새로고침 실패:', error);
    }
  };

  return (
    <ComparisonContainer>
      <HeaderActions>
        <BackButton onClick={handleBackToHome}>
          ← 홈으로 돌아가기
        </BackButton>
        
        <RefreshButton onClick={handleRefreshData} disabled={loading}>
          {loading ? '새로고침 중...' : '🔄 데이터 새로고침'}
        </RefreshButton>
      </HeaderActions>
      
      <PageTitle>
        {selectedCountries.length > 0 
          ? `선택된 ${selectedCountries.length}개국 실시간 환율 및 물가 지수 비교`
          : '국가별 실시간 환율 및 물가 지수 비교'
        }
      </PageTitle>
      
      <ChartSection>
        <SectionTitle>환율 차트</SectionTitle>
        <ExchangeRateChart />
      </ChartSection>

      {selectedCountries.length > 0 ? (
        <CountriesGrid>
          {selectedCountries.map(countryCode => (
            <CountryCard key={countryCode} country={countryCode} />
          ))}
        </CountriesGrid>
      ) : (
        <NoCountriesMessage>
          비교할 국가가 선택되지 않았습니다.
          <br />
          홈페이지에서 국가를 선택한 후 다시 시도해주세요.
        </NoCountriesMessage>
      )}
    </ComparisonContainer>
  );
};

export default ComparisonPage;
