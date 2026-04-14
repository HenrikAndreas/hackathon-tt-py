# TypeScript AST Specification for Ghostfolio Translation

Analysis of `apps/api/` (264 files) and `libs/common/` (163 files) from ghostfolio backend.
Key translation target: `portfolio-calculator.ts` (1173 lines), `roai/portfolio-calculator.ts` (1009 lines), `rule.ts` (82 lines).

---

## 1. Program Structure

### AST Node: `Program`
- Top-level container: list of statements
- Each `.ts` file = one Program

### AST Node: `ImportDeclaration`
Named imports dominate. No default imports found in backend.

```
import { Big } from 'big.js';
import { format, isBefore } from 'date-fns';
import { cloneDeep, sortBy } from 'lodash';
import { PortfolioCalculator } from '@ghostfolio/api/app/portfolio/calculator/portfolio-calculator';
import { DATE_FORMAT } from '@ghostfolio/common/helper';
```

Variants needed:
- `import { A, B } from 'module'` — named imports
- `import { A as B } from 'module'` — aliased imports
- `import * as X from 'module'` — namespace imports (rare but present)

### AST Node: `ExportDeclaration`
```
export class RoaiPortfolioCalculator extends PortfolioCalculator { }
export const DATE_FORMAT = 'yyyy-MM-dd';
export function capitalize(s: string) { }
export interface SymbolMetrics { }
export type BenchmarkTrend = 'DOWN' | 'NEUTRAL' | 'UP';
export enum PerformanceCalculationType { }
export { PortfolioSnapshot, TimelinePosition };  // re-exports
export * from './types';  // barrel re-exports
```

---

## 2. Declarations

### AST Node: `VariableDeclaration`
```
const x = 5;
let y = 'hello';
const DATE_FORMAT = 'yyyy-MM-dd';
```
- `kind`: `const` | `let` | `var`
- `declarators`: list of `{ name, type_annotation?, initializer? }`

### AST Node: `FunctionDeclaration`
```
export function calculateBenchmarkTrend({ days, historicalData }: { days: number; historicalData: MarketData[] }): BenchmarkTrend { }
export function capitalize(aString: string) { }
```
- `name`, `params` (with destructuring), `return_type?`, `body`, `async?`, `export?`

### AST Node: `ArrowFunction`
Extremely heavy usage (368 array method callbacks alone).
```
(x) => x + 1
({ marketPrice }) => new Big(marketPrice)
async () => { ... }
```
- `params`, `body` (expression or block), `async?`

---

## 3. Type System

### AST Node: `TypeAnnotation`
```
key: string
days: number
hasErrors: boolean
prices: Big[]
holdings: PortfolioPosition[]
value: { [key: string]: string }
```

### AST Node: `TypeAlias`
```
export type BenchmarkTrend = 'DOWN' | 'NEUTRAL' | 'UNKNOWN' | 'UP';
export type GroupBy = 'month' | 'year';
export type DateRange = '1d' | '1w' | '1m' | '3m' | '6m' | 'ytd' | '1y' | '5y' | 'max';
export type RequestWithUser = Request & { user: UserWithSettings };
export type AccountWithPlatform = Account & { platform?: Platform };
```

Types to support:
- **Primitive types**: `string`, `number`, `boolean`, `void`, `null`, `undefined`, `any`, `never`
- **Array types**: `T[]`, `Array<T>`
- **Union types**: `A | B | C`
- **Intersection types**: `A & B`
- **Literal types**: `'UP'`, `'DOWN'`, `42`
- **Object literal types**: `{ key: string; value: number }`
- **Index signature types**: `{ [key: string]: Big }`, `{ [date: string]: Big }`
- **Optional properties**: `platform?: Platform`
- **Tuple types**: (minimal usage)

### AST Node: `GenericType`
```
Promise<string>
Promise<string[]>
Partial<SymbolProfile>
Map<string, string>
Record<string, PublicRoute>
Rule<T extends RuleSettings>
Array.from<...>
```

### AST Node: `TypeAssertion`
```
return [id, marketData] as const;
```

---

## 4. Interfaces

### AST Node: `InterfaceDeclaration`
~50+ interfaces in `libs/common/src/lib/interfaces/`. Critical for data shapes.

```
export interface SymbolMetrics {
  currentValues: { [date: string]: Big };
  grossPerformance: Big;
  hasErrors: boolean;
  netPerformancePercentageWithCurrencyEffectMap: { [key: DateRange]: Big };
  // ... 30+ fields
}

export interface Activity extends Order {
  // extends another interface
}

export interface HoldingWithParents extends Holding {
  parents: { ... }
}
```

Properties:
- `name: Type`
- `name?: Type` (optional)
- `readonly name: Type`
- Index signatures: `[key: string]: Type`
- Extends other interfaces

---

## 5. Enums

### AST Node: `EnumDeclaration`
```
export enum PerformanceCalculationType {
  ROI = 'ROI',
  ROAI = 'ROAI',
  MWR = 'MWR',
  TWR = 'TWR'
}

export enum SubscriptionType { ... }
```
- String enums (primary pattern)
- Numeric enums (possible)

---

## 6. Classes

### AST Node: `ClassDeclaration`
Heavily used. Core pattern in entire backend.

```
export abstract class PortfolioCalculator {
  protected static readonly ENABLE_LOGGING = false;

  protected accountBalanceItems: HistoricalDataItem[];
  private currency: string;
  private snapshot: PortfolioSnapshot;

  public constructor({ accountBalanceItems, activities, ... }: { ... }) {
    this.accountBalanceItems = accountBalanceItems;
  }

  protected abstract calculateOverallPerformance(positions: TimelinePosition[]): PortfolioSnapshot;
  protected abstract getPerformanceCalculationType(): PerformanceCalculationType;

  public async getSnapshot(): Promise<PortfolioSnapshot> { ... }
}
```

```
export class RoaiPortfolioCalculator extends PortfolioCalculator {
  private chartDates: string[];
  protected calculateOverallPerformance(positions: TimelinePosition[]): PortfolioSnapshot { ... }
}
```

```
export abstract class Rule<T extends RuleSettings> implements RuleInterface<T> {
  public abstract evaluate(aRuleSettings: T): EvaluationResult;
}
```

Class features needed:
- **Property modifiers**: `public`, `private`, `protected`, `readonly`, `static`
- **Constructor**: with parameter properties, destructured params
- **Methods**: regular, `async`, `abstract`
- **Inheritance**: `extends BaseClass`
- **Interface implementation**: `implements InterfaceA, InterfaceB`
- **Abstract classes & methods**
- **Generics on classes**: `Rule<T extends RuleSettings>`
- **Static properties/methods**: `static readonly ENABLE_LOGGING = false`

### AST Node: `Decorator`
NestJS decorators throughout controllers/services:
```
@Controller('platforms')
@Injectable()
@Module({ imports: [...], controllers: [...], providers: [...] })
@Get()
@Post()
@Put()
@Delete()
@UseGuards(AuthGuard('jwt'), HasPermissionGuard)
@HasPermission(permissions.readPlatforms)
@Inject(REQUEST)
@Body()
@Param('id')
@Query('symbol')
```
- Class decorators
- Method decorators
- Parameter decorators
- Decorator factories (with arguments)

---

## 7. Expressions

### AST Node: `BinaryExpression`
```
a + b, a - b, a * b, a / b
a === b, a !== b, a > b, a < b, a >= b, a <= b
a && b, a || b
a ?? b  // nullish coalescing (heavy usage)
```

### AST Node: `UnaryExpression`
```
!value
-number
typeof x
```

### AST Node: `MemberExpression`
```
this.currency
object.property
array[0]
obj?.property  // optional chaining (very heavy usage)
obj?.[0]       // optional indexed access
```

### AST Node: `CallExpression`
```
this.method(arg1, arg2)
functionName(arg)
new Big(0)
new Date()
new Map<string, string>()
new Error('message')
Promise.all([...])
Promise.race([...])
Object.keys(obj)
Object.values(obj)
Object.entries(obj)
JSON.parse(value)
JSON.stringify(data)
Array.from(set)
Array.isArray(x)
```

### AST Node: `NewExpression`
```
new Big(0)
new Date()
new Map<string, string>()
new Error('message')
```

### AST Node: `TemplateLiteral`
```
`portfolio-snapshot-${userId}`
`${portfolioSnapshotKey}-${filtersHash}`
`redis://${redisPassword ? `:${redisPassword}` : ''}@${host}:${port}/${db}`
```
- Nested expressions including ternaries inside template literals

### AST Node: `ObjectExpression`
```
{ name: 'asc' }
{ ...activity, dataSource: encodedDataSource }
{ key, languageCode = DEFAULT_LANGUAGE_CODE }
```
- Shorthand properties: `{ days }`
- Spread: `{ ...obj }`
- Computed properties: `{ [key]: value }`

### AST Node: `ArrayExpression`
```
[1, 2, 3]
[...array1, ...array2]
```

### AST Node: `SpreadExpression`
```
...args
{ ...activity, dataSource: x }
[...array1, ...array2]
```

### AST Node: `TernaryExpression`
Heavy usage throughout:
```
condition ? valueA : valueB
currency ? true : false
```

### AST Node: `Destructuring`
Object destructuring (very common):
```
const { headers, user } = request;
const { chart } = await this.portfolioService.getPerformance({...});
```
Array destructuring:
```
const [symbol, data] = entry;
for (const [key, value] of Object.entries(obj)) { }
```
Parameter destructuring:
```
function calc({ days, prices }: { days: number; prices: Big[] }) { }
```

---

## 8. Control Flow

### AST Node: `IfStatement`
```
if (condition) { } else if (other) { } else { }
```

### AST Node: `SwitchStatement`
```
switch (calculationType) {
  case 'ROI': return new RoiCalculator(...);
  case 'ROAI': return new RoaiCalculator(...);
  default: throw new Error('Unknown type');
}
```

### AST Node: `ForOfStatement`
Primary loop pattern:
```
for (const currentPosition of positions) { }
for (const [symbol, data] of Object.entries(obj)) { }
for await (const [key] of this.client.iterator({})) { }  // async iteration
```

### AST Node: `ForStatement`
Classic for loops (rare):
```
for (let i = 0; i < length; i++) { }
```

### AST Node: `WhileStatement`
```
while (condition) { }
```

### AST Node: `TryCatchStatement`
```
try {
  // ...
} catch (error) {
  Logger.error(error?.message, 'ServiceName');
} finally {
  // ...
}
```

### AST Node: `ThrowStatement`
```
throw new Error('message');
throw new HttpException(getReasonPhrase(StatusCodes.FORBIDDEN), StatusCodes.FORBIDDEN);
```

### AST Node: `ReturnStatement`
```
return value;
return { holdings };
return 'UP';
```

---

## 9. Array/Functional Methods (CRITICAL)

368+ usages of chained array methods. Must translate to Python equivalents.

### Method Chains
```
positions.filter(({ includeInTotalAssetValue }) => includeInTotalAssetValue)
prices.reduce((prev, curr) => prev.add(curr), new Big(0))
historicalData.slice(0, days).map(({ marketPrice }) => new Big(marketPrice))
Object.values(holdings).map(({ currency, marketPrice, quantity }) => ...)
Array.from(groupBy(attribute, holdings).entries()).map(([key, objs]) => ...)
holdings.sort((a, b) => a.name.localeCompare(b.name))
```

Methods needed:
- `.map()` → list comprehension / `map()`
- `.filter()` → list comprehension / `filter()`
- `.reduce()` → `functools.reduce()`
- `.forEach()` → for loop
- `.find()` → `next(x for x in ...)`
- `.some()` → `any()`
- `.every()` → `all()`
- `.flat()` / `.flatMap()` → nested comprehension
- `.sort()` / `.toSorted()` → `sorted()`
- `.slice()` → slice notation
- `.includes()` → `in`
- `.indexOf()` → `.index()`
- `.join()` → `'sep'.join()`
- `.push()` → `.append()`
- `.concat()` → `+` / `[*a, *b]`
- `.splice()` → slice assignment
- `.entries()` → `enumerate()`

---

## 10. Async/Await

624 `await` usages. Core pattern.

### AST Node: `AwaitExpression`
```
const result = await this.service.getData();
await Promise.all(promises);
await Promise.race([operation, timeout]);
```

### AST Node: `AsyncFunction` / `AsyncMethod`
```
public async getSnapshot(): Promise<PortfolioSnapshot> { ... }
async () => { ... }
```

---

## 11. Big.js Arithmetic (CRITICAL)

932 Big.js operations. Financial precision library — must map to Python `Decimal`.

```
new Big(0)
new Big(marketPrice)
value.plus(other)
value.minus(other)
value.mul(other)
value.div(other)
value.toNumber()
value.eq(other)
value.gt(other)
value.lt(other)
value.gte(other)
value.lte(other)
value.abs()
value.cmp(other)
```

Python mapping: `decimal.Decimal` or custom wrapper.

---

## 12. Date Operations (date-fns)

38 files import date-fns. Functions used:

```
format(date, 'yyyy-MM-dd')
isBefore(dateA, dateB)
isAfter(dateA, dateB)
differenceInDays(dateA, dateB)
addMilliseconds(date, ms)
subDays(date, n)
eachDayOfInterval({ start, end })
eachYearOfInterval({ start, end })
startOfDay(date) / endOfDay(date)
startOfYear(date) / endOfYear(date)
isWithinInterval(date, { start, end })
min([date1, date2])
parseISO(dateString)
parse(dateString, format, ref)
getDate(date) / getMonth(date) / getYear(date)
isMatch(str, format)
isThisYear(date)
```

Python mapping: `datetime`, `dateutil`.

---

## 13. Lodash Operations

21 files import lodash. Functions:
```
cloneDeep(obj)       → copy.deepcopy()
sortBy(arr, key)     → sorted(arr, key=...)
isNumber(x)          → isinstance(x, (int, float))
isNil(x)             → x is None
isString(x)          → isinstance(x, str)
get(obj, path)       → nested dict access
sum(arr)             → sum()
uniqBy(arr, key)     → dict-based dedup
```

---

## 14. Module Patterns (NestJS — lower priority)

Only matters if translating controllers/services (wrapper handles this).

```
@Module({ imports: [...], controllers: [...], providers: [...], exports: [...] })
@Controller('path')
@Injectable()
```

DI constructor pattern:
```
constructor(
  private readonly serviceA: ServiceA,
  @Inject(REQUEST) private readonly request: RequestWithUser,
  @Inject(CACHE_MANAGER) private readonly cache: Cache
) {}
```

---

## 15. Miscellaneous Patterns

### Type Guards / Narrowing
```
if (currentPosition.feeInBaseCurrency) { }  // truthy check
if (isNumber(value)) { }
```

### `as const` Assertion
```
return [id, marketData] as const;
```

### Dynamic Import
```
const dynamicImport = new Function('s', 'return import(s)');
const { tablemark } = await dynamicImport('tablemark');
```

### RxJS (interceptors only)
```
import { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';
return next.handle().pipe(map(data => transform(data)));
```

### String Methods
```
str.toLowerCase()
str.toUpperCase()
str.charAt(0)
str.slice(1)
str.split(',')
str.replace(/-/g, '')
str.localeCompare(other)
str.startsWith(prefix)
```

### Object Static Methods
```
Object.keys(obj)      → list(obj.keys()) or obj.keys()
Object.values(obj)    → list(obj.values())
Object.entries(obj)   → list(obj.items())
Object.assign(t, s)   → {**t, **s}
Object.keys(o).reduce(...)
```

---

## AST Node Summary Table

| Node Type | Priority | Count/Frequency |
|-----------|----------|-----------------|
| ImportDeclaration | HIGH | Every file |
| ExportDeclaration | HIGH | Every file |
| ClassDeclaration | HIGH | ~100+ classes |
| InterfaceDeclaration | HIGH | ~50+ interfaces |
| TypeAlias | HIGH | ~25+ type aliases |
| EnumDeclaration | MEDIUM | 3 enums |
| FunctionDeclaration | HIGH | ~50+ functions |
| ArrowFunction | HIGH | 368+ callbacks |
| VariableDeclaration | HIGH | Everywhere |
| PropertyDeclaration | HIGH | All classes |
| MethodDeclaration | HIGH | All classes |
| Decorator | MEDIUM | NestJS controllers |
| CallExpression | HIGH | Everywhere |
| MemberExpression | HIGH | Everywhere |
| BinaryExpression | HIGH | Everywhere |
| TernaryExpression | HIGH | Very common |
| TemplateLiteral | HIGH | Very common |
| ObjectExpression | HIGH | Very common |
| ArrayExpression | HIGH | Very common |
| SpreadExpression | HIGH | Common |
| Destructuring | HIGH | Very common |
| IfStatement | HIGH | Everywhere |
| ForOfStatement | HIGH | Primary loop |
| SwitchStatement | MEDIUM | ~5 usages |
| TryCatchStatement | MEDIUM | ~20 usages |
| ReturnStatement | HIGH | Everywhere |
| ThrowStatement | MEDIUM | ~15 usages |
| AwaitExpression | HIGH | 624 usages |
| OptionalChaining | HIGH | Very common |
| NullishCoalescing | HIGH | Common |
| TypeAnnotation | HIGH | Everywhere |
| GenericType | HIGH | Promise<T>, Map<K,V>, etc. |
| IndexSignature | HIGH | `{ [key: string]: Big }` |
| AsConst | LOW | 1 usage |
| DynamicImport | LOW | 1 usage |
| Observable/RxJS | LOW | Interceptors only |

---

## Python Translation Strategy (Key Mappings)

| TypeScript | Python |
|-----------|--------|
| `class X extends Y` | `class X(Y):` |
| `implements I` | Protocol/ABC |
| `abstract class` | `ABC` |
| `abstract method` | `@abstractmethod` |
| `interface { }` | `TypedDict` or `@dataclass` |
| `type X = 'A' \| 'B'` | `Literal['A', 'B']` or `Enum` |
| `enum { A='a' }` | `class E(str, Enum)` |
| `Big(x).plus(y)` | `Decimal(x) + Decimal(y)` |
| `async/await` | `async/await` |
| `Promise<T>` | `Coroutine` / awaitable |
| `.map(fn)` | list comprehension |
| `.filter(fn)` | list comprehension |
| `.reduce(fn, init)` | `functools.reduce()` |
| `?.` | `getattr(obj, 'x', None)` or `obj.x if obj else None` |
| `??` | `x if x is not None else y` |
| `{ ...a, ...b }` | `{**a, **b}` |
| `[...a, ...b]` | `[*a, *b]` |
| `` `template ${x}` `` | `f"template {x}"` |
| `const { a, b } = obj` | `a, b = obj['a'], obj['b']` |
| `for (x of arr)` | `for x in arr:` |
| `try/catch` | `try/except` |
| `throw new Error()` | `raise Exception()` |
| `private/protected` | `_name` / `__name` convention |
| `readonly` | property or convention |
