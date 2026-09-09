import type { EntityRecord } from "../../types";
import { Icon } from "../../components/Icon";
import { EmptyState, StatusBadge } from "../../components/ui";
import type {
  InputLookups,
  ResourceDefinition,
} from "./input-management.types";

interface ResourceTableProps {
  definition: ResourceDefinition;
  items: EntityRecord[];
  lookups: InputLookups;
  onEdit: (item: EntityRecord) => void;
  onDelete: (item: EntityRecord) => void;
}

export function ResourceTable({
  definition,
  items,
  lookups,
  onEdit,
  onDelete,
}: ResourceTableProps) {
  if (!items.length) {
    return (
      <EmptyState
        icon={definition.icon}
        title={`No ${definition.title.toLowerCase()} yet`}
        description={`Add the first ${definition.singular} to continue preparing solver input.`}
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table management-table">
        <thead>
          <tr>
            {definition.columns.map((column) => (
              <th key={column.label}>{column.label}</th>
            ))}
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              {definition.columns.map((column, index) => {
                const value = column.value(item, lookups);
                return (
                  <td key={column.label}>
                    {column.badge ? (
                      <StatusBadge status={value.toUpperCase().replaceAll(" ", "_")} />
                    ) : index === 0 ? (
                      <strong>{value}</strong>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
              <td>
                <div className="management-actions">
                  <button type="button" onClick={() => onEdit(item)} title="Edit">
                    <Icon name="edit" />
                  </button>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => onDelete(item)}
                    title="Delete"
                  >
                    <Icon name="trash" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
