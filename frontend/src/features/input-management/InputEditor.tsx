import { useEffect, useMemo, useState, type SubmitEvent } from "react";
import type { EntityRecord } from "../../types";
import { Button, ErrorBanner, Spinner } from "../../components/ui";
import type {
  FieldDefinition,
  FormValues,
  InputLookups,
  ResourceDefinition,
} from "./input-management.types";

interface InputEditorProps {
  definition: ResourceDefinition;
  entity: EntityRecord | null;
  lookups: InputLookups;
  errorMessage?: string;
  isSaving: boolean;
  onCancel: () => void;
  onSave: (payload: Record<string, unknown>) => void;
}

function initialValues(
  definition: ResourceDefinition,
  entity: EntityRecord | null,
): FormValues {
  if (!entity) return { ...definition.defaults };
  return Object.fromEntries(
    definition.fields.map((field) => [
      field.key,
      (entity[field.key] as FormValues[string]) ?? "",
    ]),
  );
}

function Field({
  field,
  value,
  values,
  lookups,
  onChange,
}: {
  field: FieldDefinition;
  value: FormValues[string];
  values: FormValues;
  lookups: InputLookups;
  onChange: (value: FormValues[string]) => void;
}) {
  if (field.visible && !field.visible(values)) return null;

  if (field.type === "checkbox") {
    return (
      <label className="management-check">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>
          <strong>{field.label}</strong>
          {field.help && <small>{field.help}</small>}
        </span>
      </label>
    );
  }

  const options = field.options?.(lookups) ?? [];
  return (
    <label className="management-field">
      <span>{field.label}{field.required && <em>*</em>}</span>
      {field.type === "select" ? (
        <select
          value={String(value ?? "")}
          required={field.required}
          onChange={(event) => {
            const selected = event.target.value;
            const option = options.find((item) => String(item.value) === selected);
            onChange(option?.value ?? "");
          }}
        >
          <option value="">{field.required ? "Select an option" : "None"}</option>
          {options.map((option) => (
            <option key={String(option.value)} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={field.type}
          value={String(value ?? "")}
          required={field.required}
          min={field.min}
          max={field.max}
          step={field.step ?? (field.type === "number" ? 1 : undefined)}
          onChange={(event) =>
            onChange(
              field.type === "number" && event.target.value !== ""
                ? Number(event.target.value)
                : event.target.value,
            )
          }
        />
      )}
      {field.help && <small>{field.help}</small>}
    </label>
  );
}

export function InputEditor({
  definition,
  entity,
  lookups,
  errorMessage,
  isSaving,
  onCancel,
  onSave,
}: InputEditorProps) {
  const seed = useMemo(
    () => initialValues(definition, entity),
    [definition, entity],
  );
  const [values, setValues] = useState<FormValues>(seed);

  useEffect(() => setValues(seed), [seed]);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const nullableFields = new Set([
      "parent_group_id",
      "expected_students",
      "max_students",
      "required_room_type",
      "required_room_id",
      "preference_weight",
    ]);
    const visibleFields = definition.fields.filter(
      (field) => !field.visible || field.visible(values),
    );
    const payload = Object.fromEntries(visibleFields.flatMap((field) => {
      const value = values[field.key];
      if (value === "" || value === undefined) {
        return nullableFields.has(field.key) ? [[field.key, null]] : [];
      }
      return [[field.key, value]];
    }));

    if (
      (definition.key === "staff-availability" ||
        definition.key === "room-availability") &&
      (values.availability_type === "AVAILABLE" ||
        values.availability_type === "UNAVAILABLE")
    ) {
      payload.preference_weight = null;
    }
    onSave(payload);
  }

  return (
    <form className="management-form" onSubmit={submit}>
      {errorMessage && <ErrorBanner message={errorMessage} />}
      <div className="management-form__grid">
        {definition.fields.map((field) => (
          <Field
            key={field.key}
            field={field}
            value={values[field.key]}
            values={values}
            lookups={lookups}
            onChange={(value) =>
              setValues((current) => ({ ...current, [field.key]: value }))
            }
          />
        ))}
      </div>
      <footer className="modal__actions">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? <><Spinner small /> Saving…</> : entity ? "Save changes" : `Add ${definition.singular}`}
        </Button>
      </footer>
    </form>
  );
}
