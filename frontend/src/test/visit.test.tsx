import { render, screen, fireEvent } from '@testing-library/react';
import { expect, it } from 'vitest';
import { VisitPanel } from '../VisitPanel';
it('separates family diagnoses, uncertainty and medication events with full evidence', () => {
  render(<VisitPanel version={3} pages={[{ pageNumber: 2 }]} visit={{ candidateBlocks: 4, processedBlocks: ['b1'], issues: [{ code: 'REJECTED_CANDIDATE' }], statements: [
    { name: 'диабет', kind: 'CONDITION', subject: 'FAMILY', assertion: 'CONFIRMED', medicationState: 'NOT_APPLICABLE', temporality: 'HISTORICAL', sourceText: 'У матери был диабет.', contextText: 'У матери был диабет. У пациента пока не подтверждён.', source: { pageIndex: 0 } },
    { name: 'Аторвастатин', kind: 'MEDICATION', subject: 'PATIENT', assertion: 'UNKNOWN', medicationState: 'NOT_STARTED', temporality: 'CURRENT', sourceText: 'Аторвастатин не начал.', contextText: 'Аторвастатин не начал.', source: { pageIndex: 0 } },
  ] }} />);
  expect(screen.getByText('Родственник')).toBeVisible();
  expect(screen.getByText('Не начал приём')).toBeVisible();
  expect(screen.getByText(/Проблемы извлечения: 1/)).toBeVisible();
  expect(screen.getByText(/Ваши исправления/)).toBeVisible();
  fireEvent.click(screen.getAllByText('Цитата и контекст')[0]);
  expect(screen.getByText('У матери был диабет. У пациента пока не подтверждён.')).toBeVisible();
});
