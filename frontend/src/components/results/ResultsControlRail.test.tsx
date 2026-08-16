import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ResultsControlRail from './ResultsControlRail';
import type { CategorizedVectors } from '../../types';

const SAMPLE: CategorizedVectors = {
  field_rates: ['FOPR', 'FWPR'],
  field_cumulative: ['FOPT'],
  field_derived: [],
  well_rates: { PROD1: ['WOPR', 'WBHP'], PROD2: ['WOPR'] },
  well_cumulative: {},
  well_injection: { INJ1: ['WGIR'] },
  wells: ['PROD1', 'PROD2', 'INJ1'],
};

const DEFAULT_PROPS = {
  categorized: SAMPLE,
  selectedWells: new Set(['PROD1']),
  onWells: vi.fn(),
  selectedVectors: {
    field_rates: new Set(['FOPR']),
    field_cumulative: new Set(),
    field_derived: new Set(),
    well_rates: new Set(),
    well_cumulative: new Set(),
    well_injection: new Set(),
  },
  onVectors: vi.fn(),
  logScale: false,
  onLogScale: vi.fn(),
  gridLayout: '2col' as const,
  onGridLayout: vi.fn(),
  perProperty: false,
  onPerProperty: vi.fn(),
  unitSystem: 'FIELD' as const,
  onUnitSystem: vi.fn(),
};

describe('ResultsControlRail', () => {
  it('renders well checkboxes for each well', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText('PROD1')).toBeInTheDocument();
    expect(screen.getByLabelText('PROD2')).toBeInTheDocument();
    expect(screen.getByLabelText('INJ1')).toBeInTheDocument();
  });

  it('calls onWells when a well checkbox is clicked', () => {
    const onWells = vi.fn();
    render(<ResultsControlRail {...DEFAULT_PROPS} onWells={onWells} selectedWells={new Set()} />);
    fireEvent.click(screen.getByLabelText('PROD1'));
    expect(onWells).toHaveBeenCalledTimes(1);
    const newSet = onWells.mock.calls[0][0];
    expect(newSet.has('PROD1')).toBe(true);
  });

  it('shows log-scale toggle', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/log scale/i)).toBeInTheDocument();
  });

  it('groups wells by role (PROD vs INJ)', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByText(/producers/i)).toBeInTheDocument();
    expect(screen.getByText(/injectors/i)).toBeInTheDocument();
  });

  it('shows grid layout selector', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/grid columns/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('2 columns')).toBeInTheDocument();
  });

  it('shows per-property toggle', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/per-property/i)).toBeInTheDocument();
  });

  it('shows unit system selector', () => {
    render(<ResultsControlRail {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText(/unit system/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/field.*stb.*mscf.*psia/i)).toBeInTheDocument();
  });

  it('calls onGridLayout when selector changes', () => {
    const onGridLayout = vi.fn();
    render(<ResultsControlRail {...DEFAULT_PROPS} onGridLayout={onGridLayout} />);
    fireEvent.change(screen.getByLabelText(/grid columns/i), { target: { value: '4col' } });
    expect(onGridLayout).toHaveBeenCalledWith('4col');
  });

  it('calls onPerProperty when toggle changes', () => {
    const onPerProperty = vi.fn();
    render(<ResultsControlRail {...DEFAULT_PROPS} onPerProperty={onPerProperty} />);
    fireEvent.click(screen.getByLabelText(/per-property/i));
    expect(onPerProperty).toHaveBeenCalledWith(true);
  });

  it('calls onUnitSystem when selector changes', () => {
    const onUnitSystem = vi.fn();
    render(<ResultsControlRail {...DEFAULT_PROPS} onUnitSystem={onUnitSystem} />);
    fireEvent.change(screen.getByLabelText(/unit system/i), { target: { value: 'METRIC' } });
    expect(onUnitSystem).toHaveBeenCalledWith('METRIC');
  });
});