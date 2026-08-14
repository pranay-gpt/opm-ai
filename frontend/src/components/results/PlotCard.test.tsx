import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlotCard from './PlotCard';

vi.mock('plotly.js-dist-min', () => ({
  default: {
    newPlot: vi.fn(),
    purge: vi.fn(),
    relayout: vi.fn(),
    downloadImage: vi.fn(),
  },
}));

describe('PlotCard', () => {
  it('renders the plot name', () => {
    render(<PlotCard jobId="j1" plotName="Production Rates" plotJson="" />);
    expect(screen.getByText('Production Rates')).toBeInTheDocument();
  });

  it('shows empty state when plotJson is empty', () => {
    render(<PlotCard jobId="j1" plotName="Empty" plotJson="" />);
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  it('renders the Export menu when exportGroup provided', () => {
    render(
      <PlotCard
        jobId="j1"
        plotName="Foo"
        plotJson=""
        exportGroup="field_rates"
        exportVectors={['FOPR']}
      />
    );
    expect(screen.getByText(/export/i)).toBeInTheDocument();
  });

  it('uses the resolved theme', () => {
    render(<PlotCard jobId="j1" plotName="Foo" plotJson="" />);
    // Just verifies the component renders without throwing on theme access.
    expect(screen.getByText('Foo')).toBeInTheDocument();
  });

  it('hides export menu when exportGroup not provided', () => {
    render(<PlotCard jobId="j1" plotName="Foo" plotJson="" />);
    expect(screen.queryByText(/Export/)).not.toBeInTheDocument();
  });

  it('shows export menu when exportGroup provided', () => {
    render(
      <PlotCard
        jobId="j1"
        plotName="Foo"
        plotJson=""
        exportGroup="field_rates"
        exportVectors={['FOPR']}
      />
    );
    expect(screen.getByText('Export')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Export'));
    expect(screen.getByText('PNG')).toBeInTheDocument();
    expect(screen.getByText('SVG')).toBeInTheDocument();
    expect(screen.getByText(/CSV \(native\)/)).toBeInTheDocument();
    expect(screen.getByText(/CSV \(monthly\)/)).toBeInTheDocument();
    expect(screen.getByText(/CSV \(yearly\)/)).toBeInTheDocument();
  });
});