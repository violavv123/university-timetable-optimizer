import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useParams } from "react-router-dom";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import {
  Button,
  ErrorBanner,
  PageHeader,
  Spinner,
} from "../components/ui";
import { InputEditor } from "../features/input-management/InputEditor";
import { inputResources } from "../features/input-management/input-config";
import { ResourceTable } from "../features/input-management/ResourceTable";
import { useInputLookups } from "../features/input-management/useInputLookups";
import { getErrorMessage } from "../lib/api-error";
import { crudService } from "../services/crud.service";
import { fetchAll } from "../services/pagination.service";
import type { EntityRecord } from "../types";
import "../styles/pages/input-management.css";

interface SaveVariables {
  id?: number;
  payload: Record<string, unknown>;
}

export function InputManagementPage() {
  const { resourceKey = "rooms" } = useParams();
  const definition = inputResources.find((item) => item.key === resourceKey);
  const queryClient = useQueryClient();
  const lookups = useInputLookups();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<EntityRecord | null | undefined>();
  const [deleting, setDeleting] = useState<EntityRecord | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    document.title = `Input management — Tempo`;
    setSearch("");
    setEditing(undefined);
    setDeleting(null);
  }, [resourceKey]);

  const records = useQuery({
    queryKey: ["managed-resource", definition?.key],
    queryFn: () => fetchAll<EntityRecord>(definition!.endpoint),
    enabled: Boolean(definition),
  });

  const save = useMutation({
    mutationFn: ({ id, payload }: SaveVariables) =>
      id
        ? crudService.update<EntityRecord>(definition!.endpoint, id, payload)
        : crudService.create<EntityRecord>(definition!.endpoint, payload),
    onSuccess: (_, variables) => {
      setEditing(undefined);
      setNotice(
        `${definition!.title} ${variables.id ? "updated" : "created"} successfully.`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["managed-resource", definition!.key],
      });
      void queryClient.invalidateQueries({ queryKey: [definition!.key] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => crudService.remove(definition!.endpoint, id),
    onSuccess: (response) => {
      setDeleting(null);
      setNotice(response.message);
      void queryClient.invalidateQueries({
        queryKey: ["managed-resource", definition!.key],
      });
      void queryClient.invalidateQueries({ queryKey: [definition!.key] });
    },
  });

  const filtered = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return records.data ?? [];
    return (records.data ?? []).filter((item) =>
      Object.values(item).some((value) =>
        String(value ?? "").toLowerCase().includes(normalized),
      ),
    );
  }, [records.data, search]);

  if (!definition) return <Navigate to="/inputs/rooms" replace />;

  return (
    <div className="page input-management-page">
      <PageHeader
        eyebrow="Operational data"
        title="Input management"
        description="Maintain the term-specific information used by the timetable solver. Academic reference data remains stable and is used in the selectors."
        actions={
          <Link to="/assignments"><Button variant="secondary" icon="users">Teaching assignments</Button></Link>
        }
      />

      {notice && (
        <div className="success-banner">
          <Icon name="check" />
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice("")}>
            <Icon name="x" />
          </button>
        </div>
      )}
      {lookups.error && <ErrorBanner message={getErrorMessage(lookups.error)} />}

      <div className="management-layout">
        <aside className="management-nav panel">
          <p>Academic setup</p>
          {inputResources.slice(0, 1).map((resource) => (
            <Link
              key={resource.key}
              to={`/inputs/${resource.key}`}
              className={resource.key === definition.key ? "active" : ""}
            >
              <Icon name={resource.icon} />
              <span>{resource.title}</span>
            </Link>
          ))}
          <p>Resources</p>
          {inputResources.slice(1, 5).map((resource) => (
            <Link
              key={resource.key}
              to={`/inputs/${resource.key}`}
              className={resource.key === definition.key ? "active" : ""}
            >
              <Icon name={resource.icon} />
              <span>{resource.title}</span>
            </Link>
          ))}
          <p>Solver configuration</p>
          {inputResources.slice(5).map((resource) => (
            <Link
              key={resource.key}
              to={`/inputs/${resource.key}`}
              className={resource.key === definition.key ? "active" : ""}
            >
              <Icon name={resource.icon} />
              <span>{resource.title}</span>
            </Link>
          ))}
        </aside>

        <section className="management-content panel">
          <header className="management-content__header">
            <div>
              <div className="management-title">
                <span><Icon name={definition.icon} /></span>
                <div>
                  <h2>{definition.title}</h2>
                  <p>{definition.description}</p>
                </div>
              </div>
            </div>
            <Button icon="plus" onClick={() => setEditing(null)}>
              Add {definition.singular}
            </Button>
          </header>

          <div className="management-toolbar">
            <div className="search-box">
              <span>⌕</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={`Search ${definition.title.toLowerCase()}…`}
              />
            </div>
            <span>
              {filtered.length} of {records.data?.length ?? 0} records
            </span>
            <button
              type="button"
              className="icon-button"
              onClick={() => records.refetch()}
              aria-label="Refresh records"
            >
              <Icon name="refresh" />
            </button>
          </div>

          {records.isLoading || lookups.isLoading ? (
            <div className="inline-loader">
              <Spinner />
              <p>Loading {definition.title.toLowerCase()}…</p>
            </div>
          ) : records.error ? (
            <div className="management-error">
              <ErrorBanner message={getErrorMessage(records.error)} />
            </div>
          ) : (
            <ResourceTable
              definition={definition}
              items={filtered}
              lookups={lookups.data}
              onEdit={setEditing}
              onDelete={setDeleting}
            />
          )}
        </section>
      </div>

      {editing !== undefined && (
        <Modal
          title={editing ? `Edit ${definition.singular}` : `Add ${definition.singular}`}
          description={definition.description}
          onClose={() => setEditing(undefined)}
        >
          <InputEditor
            definition={definition}
            entity={editing}
            lookups={lookups.data}
            isSaving={save.isPending}
            errorMessage={save.error ? getErrorMessage(save.error) : undefined}
            onCancel={() => setEditing(undefined)}
            onSave={(payload) => save.mutate({ id: editing?.id, payload })}
          />
        </Modal>
      )}

      {deleting && (
        <Modal
          title={`Delete ${definition.singular}?`}
          description="This operation is checked by the backend and may be refused when the record is still in use."
          onClose={() => setDeleting(null)}
        >
          <div className="delete-confirmation">
            {remove.error && <ErrorBanner message={getErrorMessage(remove.error)} />}
            <p>
              You are about to delete record <strong>#{deleting.id}</strong>.
              Related timetable data will not be removed automatically.
            </p>
            <footer className="modal__actions">
              <Button variant="secondary" onClick={() => setDeleting(null)}>
                Keep record
              </Button>
              <Button
                variant="danger"
                icon="trash"
                disabled={remove.isPending}
                onClick={() => remove.mutate(deleting.id)}
              >
                {remove.isPending ? "Deleting…" : "Delete"}
              </Button>
            </footer>
          </div>
        </Modal>
      )}
    </div>
  );
}
