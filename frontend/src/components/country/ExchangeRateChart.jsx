import React from 'react';
import styled from 'styled-components';

const ChartContainer = styled.div`
  width: 100%;
  height: 400px;
  padding: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
  border-radius: 8px;
`;

const ChartTitle = styled.h3`
  color: #2c3e50;
  margin-bottom: 1rem;
  text-align: center;
`;

const TimeRangeSelector = styled.div`
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  margin-bottom: 2rem;
`;

const TimeButton = styled.button`
  padding: 0.5rem 1rem;
  border: 1px solid #e1e8ed;
  background: white;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.3s;
  color: #000000;
  
  &:hover {
    background-color: #f8f9fa;
  }
  
  &.active {
    background-color: #667eea;
    color: white;
    border-color: #667eea;
  }
`;

const PlaceholderChart = styled.div`
  width: 100%;
  height: 300px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.2rem;
  font-weight: bold;
`;

const ExchangeRateChart = () => {
  const [timeRange, setTimeRange] = React.useState('1D');

  const timeRanges = [
    { value: '1D', label: '1일' },
    { value: '3M', label: '최근 3개월' },
    { value: '6M', label: '최근 6개월' },
    { value: '1Y', label: '최근 1년' },
  ];

  return (
    <ChartContainer>
      <div style={{ width: '100%' }}>
        <ChartTitle>환율 차트</ChartTitle>
        
        <TimeRangeSelector>
          {timeRanges.map(range => (
            <TimeButton
              key={range.value}
              className={timeRange === range.value ? 'active' : ''}
              onClick={() => setTimeRange(range.value)}
            >
              {range.label}
            </TimeButton>
          ))}
        </TimeRangeSelector>

        <PlaceholderChart>
          📊 환율 차트 (개발 중)
        </PlaceholderChart>
      </div>
    </ChartContainer>
  );
};

export default ExchangeRateChart;
