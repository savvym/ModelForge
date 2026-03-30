import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { DatasetCreateForm } from "@/features/dataset/components/dataset-create-form";

export default async function DatasetCreatePage() {
  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
        <div className="min-w-0">
          <ConsoleBreadcrumb
            items={[
              { label: "数据集", href: "/dataset" },
              { label: "创建数据集" }
            ]}
          />
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <div className="flex h-full min-h-0">
          <div className="console-workbench__scroll min-h-0 w-full max-w-[1080px] overflow-y-auto px-5 pb-8 pt-1">
            <DatasetCreateForm />
          </div>
        </div>
      </div>
    </div>
  );
}
