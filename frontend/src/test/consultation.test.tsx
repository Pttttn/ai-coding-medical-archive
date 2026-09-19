import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReviewControls } from '../pages/Consultation';

describe('consultation review controls', () => {
  const props = { dirty: false, reviewed: false, acknowledged: false, busy: false, onAcknowledge: vi.fn(), onReview: vi.fn(), onCopy: vi.fn(), onExport: vi.fn() };
  it('requires explicit review before copy and Markdown export', () => {
    render(<ReviewControls {...props} />);
    expect(screen.getByRole('button', { name: 'Подтвердить проверку' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Markdown' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(props.onAcknowledge).toHaveBeenCalledWith(true);
  });
  it('enables export for a reviewed exact version, then locks it immediately after an edit', () => {
    const { rerender } = render(<ReviewControls {...props} reviewed acknowledged />);
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Копировать' }));
    expect(props.onCopy).toHaveBeenCalledOnce();
    rerender(<ReviewControls {...props} dirty />);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Markdown' })).toBeDisabled();
  });
  it('does not let acknowledgement skip a required save', () => {
    render(<ReviewControls {...props} dirty acknowledged />);
    expect(screen.getByRole('button', { name: 'Подтвердить проверку' })).toBeDisabled();
  });
});
