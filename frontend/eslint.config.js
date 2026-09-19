import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { parser: tseslint.parser, parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } } },
    rules: {
      'no-debugger': 'error',
      'no-unreachable': 'error',
      'valid-typeof': 'error',
      'no-duplicate-imports': ['error', { allowSeparateTypeImports: true }],
      'constructor-super': 'error',
      'no-unsafe-finally': 'error',
      'no-constant-binary-expression': 'error',
    },
  },
);
