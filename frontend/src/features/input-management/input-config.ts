import { DAY_NAMES, humanize } from "../../lib/format";
import type {
  ColumnDefinition,
  FieldDefinition,
  InputLookups,
  ResourceDefinition,
  SelectOption,
} from "./input-management.types";

const enumOptions = (...values: string[]): SelectOption[] =>
  values.map((value) => ({ value, label: humanize(value) }));

const days = Object.entries(DAY_NAMES).map(([value, label]) => ({
  value: Number(value),
  label,
}));

const idOptions = <T extends { id: number }>(
  values: T[],
  label: (value: T) => string,
): SelectOption[] =>
  values.map((value) => ({ value: value.id, label: label(value) }));

const select = (
  key: string,
  label: string,
  options: (lookups: InputLookups) => SelectOption[],
  required = true,
): FieldDefinition => ({ key, label, type: "select", options, required });

const text = (key: string, label: string, required = true): FieldDefinition => ({
  key,
  label,
  type: "text",
  required,
});

const number = (
  key: string,
  label: string,
  min = 0,
  required = true,
): FieldDefinition => ({ key, label, type: "number", min, required });

const column = (
  label: string,
  value: ColumnDefinition["value"],
  badge = false,
): ColumnDefinition => ({ label, value, badge });

const facultyOptions = (data: InputLookups) =>
  idOptions(data.faculties, (item) => `${item.code} — ${item.name}`);
const termOptions = (data: InputLookups) =>
  idOptions(data.terms, (item) => item.name);
const roomOptions = (data: InputLookups) =>
  idOptions(data.rooms, (item) => `${item.code} — ${item.capacity} seats`);
const staffOptions = (data: InputLookups) =>
  idOptions(data.staff, (item) => `${item.first_name} ${item.last_name}`);
const profileOptions = (data: InputLookups) =>
  idOptions(data.profiles, (item) => item.name);
const groupOptions = (data: InputLookups) =>
  idOptions(data.groups, (item) => item.name);
const semesterOptions = (data: InputLookups) =>
  idOptions(data.semesters, (semester) => {
    const program = data.programs.find((item) => item.id === semester.study_program_id);
    return `${program?.code ?? "Program"} · Semester ${semester.semester_number}`;
  });
const curriculumOptions = (data: InputLookups) =>
  idOptions(data.curricula, (curriculum) => {
    const course = data.courses.find((item) => item.id === curriculum.course_id);
    return `${course?.code ?? "Course"} — ${course?.name ?? curriculum.id}`;
  });
const offeringOptions = (data: InputLookups) =>
  idOptions(data.offerings, (offering) => {
    const curriculum = data.curricula.find(
      (item) => item.id === offering.curriculum_course_id,
    );
    const course = data.courses.find((item) => item.id === curriculum?.course_id);
    return `${course?.code ?? "Offering"} · ${offering.status}`;
  });

const availabilityFields = (
  resource: "staff" | "room",
): FieldDefinition[] => [
  select(
    resource === "staff" ? "staff_member_id" : "room_id",
    resource === "staff" ? "Staff member" : "Room",
    resource === "staff" ? staffOptions : roomOptions,
  ),
  select("academic_term_id", "Academic term", termOptions),
  { key: "day_of_week", label: "Day", type: "select", options: () => days, required: true },
  { key: "start_time", label: "Start time", type: "time", required: true },
  { key: "end_time", label: "End time", type: "time", required: true },
  {
    key: "availability_type",
    label: "Availability",
    type: "select",
    options: () => enumOptions("AVAILABLE", "UNAVAILABLE", "PREFERRED", "AVOID"),
    required: true,
  },
  {
    key: "preference_weight",
    label: "Preference weight",
    type: "number",
    min: 0,
    required: true,
    help: "Required only for Preferred and Avoid windows.",
    visible: (values) =>
      values.availability_type === "PREFERRED" ||
      values.availability_type === "AVOID",
  },
];

export const inputResources: ResourceDefinition[] = [
  {
    key: "faculties",
    title: "Faculties",
    singular: "faculty",
    description: "Faculty records used to separate programs, rooms and scheduling profiles.",
    endpoint: "/academic/faculties",
    icon: "home",
    defaults: {
      code: "",
      name: "",
      is_active: true,
    },
    fields: [
      text("code", "Faculty code"),
      text("name", "Faculty name"),
      { key: "is_active", label: "Active", type: "checkbox" },
    ],
    columns: [
      column("Code", (item) => String(item.code)),
      column("Faculty", (item) => String(item.name)),
      column("Status", (item) => (item.is_active ? "Active" : "Inactive"), true),
    ],
  },
  {
    key: "rooms",
    title: "Rooms",
    singular: "room",
    description: "Teaching spaces, capacities and laboratory requirements.",
    endpoint: "/resources/rooms",
    icon: "grid",
    defaults: {
      faculty_id: "",
      code: "",
      name: "",
      capacity: 40,
      room_type: "GENERAL_ROOM",
      status: "ACTIVE",
    },
    fields: [
      select("faculty_id", "Faculty", facultyOptions),
      text("code", "Room code"),
      text("name", "Display name"),
      number("capacity", "Capacity", 1),
      select("room_type", "Room type", () =>
        enumOptions("GENERAL_ROOM", "LABORATORY"),
      ),
      select("status", "Status", () =>
        enumOptions("ACTIVE", "INACTIVE", "MAINTENANCE"),
      ),
    ],
    columns: [
      column("Code", (item) => String(item.code)),
      column("Room", (item) => String(item.name)),
      column("Capacity", (item) => `${item.capacity} seats`),
      column("Type", (item) => humanize(String(item.room_type))),
      column("Status", (item) => humanize(String(item.status)), true),
    ],
  },
  {
    key: "student-groups",
    title: "Student groups",
    singular: "student group",
    description: "Cohorts and lecture, exercise or laboratory subdivisions.",
    endpoint: "/resources/student-groups",
    icon: "users",
    defaults: {
      program_semester_id: "",
      academic_term_id: "",
      parent_group_id: "",
      name: "",
      group_type: "COHORT",
      student_count: 1,
      is_active: true,
    },
    fields: [
      select("program_semester_id", "Program semester", semesterOptions),
      select("academic_term_id", "Academic term", termOptions),
      select("parent_group_id", "Parent group (optional)", groupOptions, false),
      text("name", "Group name"),
      select("group_type", "Group type", () =>
        enumOptions("COHORT", "LECTURE_GROUP", "NUMERICAL_GROUP", "LAB_GROUP"),
      ),
      number("student_count", "Number of students", 1),
      { key: "is_active", label: "Active", type: "checkbox" },
    ],
    columns: [
      column("Group", (item) => String(item.name)),
      column("Type", (item) => humanize(String(item.group_type))),
      column("Students", (item) => String(item.student_count)),
      column("Status", (item) => (item.is_active ? "Active" : "Inactive"), true),
    ],
  },
  {
    key: "staff-availability",
    title: "Staff availability",
    singular: "staff availability window",
    description: "Hard availability and weighted teaching preferences.",
    endpoint: "/resources/staff-availability",
    icon: "clock",
    defaults: {
      staff_member_id: "",
      academic_term_id: "",
      day_of_week: 1,
      start_time: "08:00",
      end_time: "15:00",
      availability_type: "AVAILABLE",
      preference_weight: "",
    },
    fields: availabilityFields("staff"),
    columns: [
      column("Staff", (item, data) => {
        const person = data.staff.find((value) => value.id === item.staff_member_id);
        return person ? `${person.first_name} ${person.last_name}` : `Staff #${item.staff_member_id}`;
      }),
      column("Day", (item) => DAY_NAMES[Number(item.day_of_week) as keyof typeof DAY_NAMES]),
      column("Window", (item) => `${String(item.start_time).slice(0, 5)}–${String(item.end_time).slice(0, 5)}`),
      column("Type", (item) => humanize(String(item.availability_type)), true),
    ],
  },
  {
    key: "room-availability",
    title: "Room availability",
    singular: "room availability window",
    description: "Operating hours, closures and preferred room windows.",
    endpoint: "/resources/room-availability",
    icon: "calendar",
    defaults: {
      room_id: "",
      academic_term_id: "",
      day_of_week: 1,
      start_time: "08:00",
      end_time: "20:00",
      availability_type: "AVAILABLE",
      preference_weight: "",
    },
    fields: availabilityFields("room"),
    columns: [
      column("Room", (item, data) => data.rooms.find((room) => room.id === item.room_id)?.code ?? `Room #${item.room_id}`),
      column("Day", (item) => DAY_NAMES[Number(item.day_of_week) as keyof typeof DAY_NAMES]),
      column("Window", (item) => `${String(item.start_time).slice(0, 5)}–${String(item.end_time).slice(0, 5)}`),
      column("Type", (item) => humanize(String(item.availability_type)), true),
    ],
  },
  {
    key: "profiles",
    title: "Scheduling profiles",
    singular: "scheduling profile",
    description: "Group-size limits and objective penalty weights.",
    endpoint: "/scheduling-input/scheduling-profiles",
    icon: "settings",
    defaults: {
      faculty_id: "",
      name: "",
      slot_minutes: 60,
      max_lecture_students: 60,
      max_numerical_students: 40,
      max_lab_students: 20,
      preferred_room_weight: 1,
      historical_room_weight: 1,
      student_gap_weight: 1,
      staff_gap_weight: 1,
      late_hour_weight: 1,
      is_active: true,
    },
    fields: [
      select("faculty_id", "Faculty", facultyOptions),
      text("name", "Profile name"),
      number("slot_minutes", "Slot duration (minutes)", 1),
      number("max_lecture_students", "Maximum lecture group", 1),
      number("max_numerical_students", "Maximum exercise group", 1),
      number("max_lab_students", "Maximum laboratory group", 1),
      number("preferred_room_weight", "Preferred-room weight"),
      number("historical_room_weight", "Historical-room weight"),
      number("student_gap_weight", "Student-gap weight"),
      number("staff_gap_weight", "Staff-gap weight"),
      number("late_hour_weight", "Late-hour weight"),
      { key: "is_active", label: "Active", type: "checkbox" },
    ],
    columns: [
      column("Profile", (item) => String(item.name)),
      column("Slot", (item) => `${item.slot_minutes} min`),
      column("Lecture max.", (item) => String(item.max_lecture_students)),
      column("Lab max.", (item) => String(item.max_lab_students)),
      column("Status", (item) => (item.is_active ? "Active" : "Inactive"), true),
    ],
  },
  {
    key: "time-slots",
    title: "Time slots",
    singular: "time slot",
    description: "The weekly grid on which sessions can begin.",
    endpoint: "/scheduling-input/time-slots",
    icon: "clock",
    defaults: {
      scheduling_profile_id: "",
      day_of_week: 1,
      slot_index: 0,
      start_time: "08:00",
      end_time: "09:00",
      is_active: true,
    },
    fields: [
      select("scheduling_profile_id", "Scheduling profile", profileOptions),
      { key: "day_of_week", label: "Day", type: "select", options: () => days, required: true },
      number("slot_index", "Slot index"),
      { key: "start_time", label: "Start time", type: "time", required: true },
      { key: "end_time", label: "End time", type: "time", required: true },
      { key: "is_active", label: "Active", type: "checkbox" },
    ],
    columns: [
      column("Profile", (item, data) => data.profiles.find((profile) => profile.id === item.scheduling_profile_id)?.name ?? "Unknown"),
      column("Day", (item) => DAY_NAMES[Number(item.day_of_week) as keyof typeof DAY_NAMES]),
      column("Index", (item) => String(item.slot_index)),
      column("Window", (item) => `${String(item.start_time).slice(0, 5)}–${String(item.end_time).slice(0, 5)}`),
      column("Status", (item) => (item.is_active ? "Active" : "Inactive"), true),
    ],
  },
  {
    key: "offerings",
    title: "Course offerings",
    singular: "course offering",
    description: "Courses activated for a specific academic term.",
    endpoint: "/scheduling-input/course-offerings",
    icon: "book",
    defaults: {
      curriculum_course_id: "",
      academic_term_id: "",
      expected_students: "",
      status: "DRAFT",
    },
    fields: [
      select("curriculum_course_id", "Curriculum course", curriculumOptions),
      select("academic_term_id", "Academic term", termOptions),
      number("expected_students", "Expected students", 1, false),
      select("status", "Status", () =>
        enumOptions("DRAFT", "READY", "CANCELLED", "COMPLETED"),
      ),
    ],
    columns: [
      column("Course", (item, data) => {
        const curriculum = data.curricula.find((value) => value.id === item.curriculum_course_id);
        return data.courses.find((course) => course.id === curriculum?.course_id)?.name ?? "Unknown course";
      }),
      column("Term", (item, data) => data.terms.find((term) => term.id === item.academic_term_id)?.name ?? "Unknown"),
      column("Students", (item) => String(item.expected_students ?? "From groups")),
      column("Status", (item) => humanize(String(item.status)), true),
    ],
  },
  {
    key: "sessions",
    title: "Course sessions",
    singular: "course session",
    description: "Recurring lectures, numerical exercises and laboratories.",
    endpoint: "/scheduling-input/course-sessions",
    icon: "calendar",
    defaults: {
      course_offering_id: "",
      name: "",
      component_type: "LECTURE",
      weekly_frequency: 1,
      duration_slots: 1,
      max_students: "",
      required_room_type: "",
      required_room_id: "",
      is_splittable: false,
      is_active: true,
    },
    fields: [
      select("course_offering_id", "Course offering", offeringOptions),
      text("name", "Session name"),
      select("component_type", "Component", () =>
        enumOptions("LECTURE", "NUMERICAL", "LABORATORY"),
      ),
      number("weekly_frequency", "Times per week", 1),
      number("duration_slots", "Duration in slots", 1),
      number("max_students", "Maximum students", 1, false),
      select("required_room_type", "Required room type", () =>
        enumOptions("GENERAL_ROOM", "LABORATORY"), false,
      ),
      select("required_room_id", "Fixed room (optional)", roomOptions, false),
      { key: "is_splittable", label: "Session may be split", type: "checkbox" },
      { key: "is_active", label: "Active", type: "checkbox" },
    ],
    columns: [
      column("Session", (item) => String(item.name)),
      column("Component", (item) => humanize(String(item.component_type))),
      column("Frequency", (item) => `${item.weekly_frequency} / week`),
      column("Duration", (item) => `${item.duration_slots} slots`),
      column("Status", (item) => (item.is_active ? "Active" : "Inactive"), true),
    ],
  },
];
