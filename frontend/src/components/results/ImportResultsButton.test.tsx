import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ImportResultsButton from './ImportResultsButton';

vi.mock('../../api/client', () => ({
  api: {
    importResults: vi.fn(),
  },
}));

import { api } from '../../api/client';

describe('ImportResultsButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a button that opens a dialog', () => {
    render(<ImportResultsButton />);
    const btn = screen.getByRole('button', { name: /import results/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText(/SMSPEC/)).toBeInTheDocument();
  });

  it('submits selected files via api.importResults', async () => {
    (api.importResults as any).mockResolvedValue({
      job_id: 'abc123',
      files_received: ['CASE.SMSPEC', 'CASE.UNSMRY'],
      warnings: [],
    });
    const onImported = vi.fn();
    render(<ImportResultsButton onImported={onImported} />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));

    const file = new File(['x'], 'CASE.SMSPEC', { type: 'application/octet-stream' });
    const input = screen.getByLabelText(/select files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(
      expect.objectContaining({ job_id: 'abc123' })
    ));
  });

  it('shows error from api.importResults', async () => {
    (api.importResults as any).mockRejectedValue(new Error('bad files'));
    render(<ImportResultsButton />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));
    const file = new File(['x'], 'CASE.SMSPEC', { type: 'application/octet-stream' });
    fireEvent.change(screen.getByLabelText(/select files/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => expect(screen.getByText(/bad files/)).toBeInTheDocument());
  });

  it('disables submit when no files selected', () => {
    render(<ImportResultsButton />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));
    const submit = screen.getByRole('button', { name: /upload/i });
    expect(submit).toBeDisabled();
  });
});