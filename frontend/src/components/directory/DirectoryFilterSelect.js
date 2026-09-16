import React from 'react';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

const ALL = '__all__';

export const DirectoryFilterSelect = ({
  id,
  label,
  value,
  placeholder,
  options,
  onChange,
  disabled = false,
}) => (
  <div className="min-w-0 space-y-2">
    <Label htmlFor={id} className="text-xs font-semibold uppercase text-slate-500">
      {label}
    </Label>
    <Select
      value={value || ALL}
      onValueChange={(nextValue) => onChange(nextValue === ALL ? '' : nextValue)}
      disabled={disabled}
    >
      <SelectTrigger id={id} data-testid={id} className="bg-white">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
);