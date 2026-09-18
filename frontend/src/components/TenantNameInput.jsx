import { useEffect, useMemo, useRef, useState } from 'react';
import { UserRound } from 'lucide-react';
import { Input } from './ui/input';

export function TenantNameInput({ value, onChange, onSelect, tenants, className, ...rest }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef(null);

  const matches = useMemo(() => {
    const needle = value.trim().toLowerCase();
    return tenants
      .filter((t) => !needle || t.name?.toLowerCase().includes(needle) || (t.mobile || '').includes(needle))
      .slice(0, 8);
  }, [tenants, value]);

  useEffect(() => {
    const onDown = (e) => { if (!wrapRef.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  useEffect(() => { setActive(0); }, [value]);

  const pick = (t) => { onSelect(t); setOpen(false); };

  const onKeyDown = (e) => {
    if (!open || matches.length === 0) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => (a + 1) % matches.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => (a - 1 + matches.length) % matches.length); }
    else if (e.key === 'Enter') { e.preventDefault(); pick(matches[active]); }
    else if (e.key === 'Escape') setOpen(false);
  };

  const show = open && matches.length > 0;

  return (
    <div ref={wrapRef} className="relative">
      <Input
        value={value}
        onChange={(e) => { onChange(e); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        autoComplete="off"
        role="combobox"
        aria-expanded={show}
        className={className}
        {...rest}
      />
      {show && (
        <ul
          role="listbox"
          data-testid="tenant-suggestions"
          className="absolute z-40 mt-1 max-h-64 w-full overflow-auto rounded-md border border-[#E6E4E0] bg-white py-1 shadow-lg"
        >
          {matches.map((t, i) => (
            <li
              key={t.id}
              role="option"
              aria-selected={i === active}
              data-testid={`tenant-suggestion-${t.id}`}
              onMouseDown={(e) => { e.preventDefault(); pick(t); }}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center gap-3 px-3 py-2 text-sm transition-colors duration-100 ${i === active ? 'bg-terracotta-50 text-terracotta-700' : 'text-stone-700'}`}
            >
              <UserRound className="h-4 w-4 shrink-0 text-stone-400" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{t.name}</div>
                <div className="truncate text-xs text-stone-500">
                  {t.mobile || 'no mobile'}{t.roomNumber ? ` · Room ${t.roomNumber}${t.bedNumber ? `/${t.bedNumber}` : ''}` : ''}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
