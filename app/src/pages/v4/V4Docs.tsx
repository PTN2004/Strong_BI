import React from 'react';
import { BookOpen } from 'lucide-react';

const V4Docs = () => {
  return (
    <div className="w-full h-full p-8 overflow-y-auto bg-transparent text-gray-800 dark:text-gray-200">
      <div className="max-w-4xl mx-auto flex flex-col gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        
        <div className="flex items-center gap-3 border-b border-gray-200 dark:border-gray-800 pb-5 mt-4">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-900/20 text-[#2563eb] flex items-center justify-center">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Tài liệu hướng dẫn (Docs)</h1>
            <p className="text-sm text-gray-500 mt-1">Cách sử dụng và hiểu các tính năng của StrongBI</p>
          </div>
        </div>
        
        <div className="flex flex-col gap-8">
          {/* Section 1 */}
          <div className="p-6 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span> 1. Sự khác biệt giữa Model V4 và V5
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700">
                <h3 className="font-semibold text-blue-600 dark:text-blue-400 mb-2">⚡ V4 (Tốc độ cao)</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                  Phiên bản tối ưu cho tốc độ. Tập trung truy xuất bảng trực tiếp để sinh SQL và trả về kết quả số liệu gần như tức thì.
                </p>
                <div className="mt-3 text-xs font-medium text-gray-500">
                  Phù hợp: Câu hỏi nhanh gọn, xem nhanh số liệu hàng ngày.
                </div>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700">
                <h3 className="font-semibold text-purple-600 dark:text-purple-400 mb-2">🚀 V5 (Phân tích sâu đa bước)</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                  Kiến trúc phân tích dữ liệu chuyên sâu. V5 sẽ đi qua các bước: trích xuất thực thể, đối chiếu ngữ nghĩa, xây dựng và duyệt đồ thị (Graph-RAG) trước khi sinh SQL. Trả về rất nhiều nội dung và insight.
                </p>
                <div className="mt-3 text-xs font-medium text-gray-500">
                  Phù hợp: Câu hỏi phân tích nguyên nhân, báo cáo phức tạp.
                </div>
              </div>
            </div>
          </div>

          {/* Section 2 */}
          <div className="p-6 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span> 2. Mẹo vẽ biểu đồ
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-4 leading-relaxed">
              Bạn có thể ép hệ thống vẽ các biểu đồ theo ý thích bằng cách đưa từ khoá vào câu hỏi. StrongBI hỗ trợ cực kỳ mạnh mẽ các biểu đồ khó:
            </p>
            <ul className="list-disc pl-5 text-sm text-gray-600 dark:text-gray-300 space-y-2">
              <li><strong>Treemap:</strong> Nhìn tỷ trọng hàng chục thành phần (VD: "Vẽ treemap doanh thu các vùng").</li>
              <li><strong>Heatmap:</strong> Xem mật độ (VD: "Vẽ heatmap đơn hàng theo khung giờ").</li>
              <li><strong>Gauge:</strong> Đo lường KPI (VD: "Tỷ lệ cửa hàng mở mới dùng gauge").</li>
              <li><strong>Combo:</strong> Hai trục Y (VD: "So sánh doanh thu (cột) và số lượng khách (đường)").</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default V4Docs;
