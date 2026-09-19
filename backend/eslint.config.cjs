const ts = require('@typescript-eslint/parser');
module.exports = [
  {ignores:['dist/**','node_modules/**','coverage/**']},
  {
    files:['src/**/*.ts','test/**/*.ts'],
    languageOptions:{parser:ts,parserOptions:{ecmaVersion:2022,sourceType:'module'}},
    rules:{
      'no-debugger':'error','no-unreachable':'error','valid-typeof':'error',
      'no-duplicate-imports':'error','no-constant-condition':['error',{checkLoops:false}],
      'no-unsafe-finally':'error','constructor-super':'off'
    }
  }
];
