export type AdherenceCell = {
  day: string;
  date: string;
  time: string;
  label: string;
  status: string;
};

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

export function AdherenceGrid({ cells }: { cells: AdherenceCell[] }) {
  const times = [...new Set(cells.map((cell) => cell.time))];
  return (
    <table aria-label="Weekly adherence">
      <caption>Weekly adherence</caption>
      <thead>
        <tr>
          <th scope="col">Time</th>
          {DAYS.map((day) => (
            <th key={day} scope="col">
              {day}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {times.map((time) => (
          <tr key={time}>
            <th scope="row">{time}</th>
            {DAYS.map((day) => {
              const cell = cells.find((item) => item.day === day && item.time === time);
              return <td key={day}>{cell ? cell.status : ""}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
