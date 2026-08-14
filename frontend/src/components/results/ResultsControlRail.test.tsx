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

describe('ResultsControlRail', () => {
  it('renders well checkboxes for each well', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set(['PROD1'])}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(['FOPR']),
          field_cumulative: new Set(),
          field_derived: new Set(),
          well_rates: new Set(),
          well_cumulative: new Set(),
          well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByLabelText('PROD1')).toBeInTheDocument();
    expect(screen.getByLabelText('PROD2')).toBeInTheDocument();
    expect(screen.getByLabelText('INJ1')).toBeInTheDocument();
  });

  it('calls onWells when a well checkbox is clicked', () => {
    const onWells = vi.fn();
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={onWells}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    fireEvent.click(screen.getByLabelText('PROD1'));
    expect(onWells).toHaveBeenCalledTimes(1);
    const newSet = onWells.mock.calls[0][0];
    expect(newSet.has('PROD1')).toBe(true);
  });

  it('shows log-scale toggle', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByLabelText(/log scale/i)).toBeInTheDocument();
  });

  it('groups wells by role (PROD vs INJ)', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByText(/producers/i)).toBeInTheDocument();
    expect(screen.getByText(/injectors/i)).toBeInTheDocument();
  });
});