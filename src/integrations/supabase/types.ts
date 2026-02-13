export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      companies: {
        Row: {
          cik: number | null
          company_id: number
          created_at: string
          description: string | null
          exchange: string | null
          logo_url: string | null
          name: string
          sector: string | null
          ticker: string
          year_founded: number | null
        }
        Insert: {
          cik?: number | null
          company_id: number
          created_at?: string
          description?: string | null
          exchange?: string | null
          logo_url?: string | null
          name: string
          sector?: string | null
          ticker: string
          year_founded?: number | null
        }
        Update: {
          cik?: number | null
          company_id?: number
          created_at?: string
          description?: string | null
          exchange?: string | null
          logo_url?: string | null
          name?: string
          sector?: string | null
          ticker?: string
          year_founded?: number | null
        }
        Relationships: []
      }
      earnings_calendar: {
        Row: {
          actual_eps: number | null
          before_after_market: string | null
          created_at: string
          difference: number | null
          estimate_eps: number | null
          fetched_at: string
          fiscal_period_end: string | null
          id: string
          percent_surprise: number | null
          report_date: string
          ticker: string
        }
        Insert: {
          actual_eps?: number | null
          before_after_market?: string | null
          created_at?: string
          difference?: number | null
          estimate_eps?: number | null
          fetched_at?: string
          fiscal_period_end?: string | null
          id?: string
          percent_surprise?: number | null
          report_date: string
          ticker: string
        }
        Update: {
          actual_eps?: number | null
          before_after_market?: string | null
          created_at?: string
          difference?: number | null
          estimate_eps?: number | null
          fetched_at?: string
          fiscal_period_end?: string | null
          id?: string
          percent_surprise?: number | null
          report_date?: string
          ticker?: string
        }
        Relationships: []
      }
      earnings_file_processing: {
        Row: {
          bucket_name: string
          created_at: string | null
          error_message: string | null
          file_exists: boolean | null
          file_size_bytes: number | null
          id: string
          processed_at: string | null
          report_date: string
          status: string | null
          ticker: string
        }
        Insert: {
          bucket_name: string
          created_at?: string | null
          error_message?: string | null
          file_exists?: boolean | null
          file_size_bytes?: number | null
          id?: string
          processed_at?: string | null
          report_date: string
          status?: string | null
          ticker: string
        }
        Update: {
          bucket_name?: string
          created_at?: string | null
          error_message?: string | null
          file_exists?: boolean | null
          file_size_bytes?: number | null
          id?: string
          processed_at?: string | null
          report_date?: string
          status?: string | null
          ticker?: string
        }
        Relationships: []
      }
      excel_processing_runs: {
        Row: {
          completed_at: string | null
          created_at: string
          data_sources_used: string[] | null
          error_message: string | null
          files_updated: number | null
          id: string
          report_date: string
          started_at: string | null
          status: string
          ticker: string
          timing: string
        }
        Insert: {
          completed_at?: string | null
          created_at?: string
          data_sources_used?: string[] | null
          error_message?: string | null
          files_updated?: number | null
          id?: string
          report_date: string
          started_at?: string | null
          status?: string
          ticker: string
          timing: string
        }
        Update: {
          completed_at?: string | null
          created_at?: string
          data_sources_used?: string[] | null
          error_message?: string | null
          files_updated?: number | null
          id?: string
          report_date?: string
          started_at?: string | null
          status?: string
          ticker?: string
          timing?: string
        }
        Relationships: []
      }
      recurring_premarket_data: {
        Row: {
          captured_at: string
          created_at: string
          crude_change: number | null
          crude_change_pct: number | null
          crude_market_time: string | null
          crude_name: string | null
          crude_open_interest: string | null
          crude_price: number | null
          crude_symbol: string | null
          crude_volume: string | null
          dow_change: number | null
          dow_change_pct: number | null
          dow_market_time: string | null
          dow_name: string | null
          dow_open_interest: string | null
          dow_price: number | null
          dow_symbol: string | null
          dow_volume: string | null
          gold_change: number | null
          gold_change_pct: number | null
          gold_market_time: string | null
          gold_name: string | null
          gold_open_interest: string | null
          gold_price: number | null
          gold_symbol: string | null
          gold_volume: string | null
          id: string
          nas_change: number | null
          nas_change_pct: number | null
          nas_market_time: string | null
          nas_name: string | null
          nas_open_interest: string | null
          nas_price: number | null
          nas_symbol: string | null
          nas_volume: string | null
          raw_gemini_response: Json | null
          screenshot_url: string | null
          silver_change: number | null
          silver_change_pct: number | null
          silver_market_time: string | null
          silver_name: string | null
          silver_open_interest: string | null
          silver_price: number | null
          silver_symbol: string | null
          silver_volume: string | null
          sp500_change: number | null
          sp500_change_pct: number | null
          sp500_market_time: string | null
          sp500_name: string | null
          sp500_open_interest: string | null
          sp500_price: number | null
          sp500_symbol: string | null
          sp500_volume: string | null
          tnote10_change: number | null
          tnote10_change_pct: number | null
          tnote10_market_time: string | null
          tnote10_name: string | null
          tnote10_open_interest: string | null
          tnote10_price: number | null
          tnote10_symbol: string | null
          tnote10_volume: string | null
          tnote2_change: number | null
          tnote2_change_pct: number | null
          tnote2_market_time: string | null
          tnote2_name: string | null
          tnote2_open_interest: string | null
          tnote2_price: number | null
          tnote2_symbol: string | null
          tnote2_volume: string | null
          tnote5_change: number | null
          tnote5_change_pct: number | null
          tnote5_market_time: string | null
          tnote5_name: string | null
          tnote5_open_interest: string | null
          tnote5_price: number | null
          tnote5_symbol: string | null
          tnote5_volume: string | null
        }
        Insert: {
          captured_at?: string
          created_at?: string
          crude_change?: number | null
          crude_change_pct?: number | null
          crude_market_time?: string | null
          crude_name?: string | null
          crude_open_interest?: string | null
          crude_price?: number | null
          crude_symbol?: string | null
          crude_volume?: string | null
          dow_change?: number | null
          dow_change_pct?: number | null
          dow_market_time?: string | null
          dow_name?: string | null
          dow_open_interest?: string | null
          dow_price?: number | null
          dow_symbol?: string | null
          dow_volume?: string | null
          gold_change?: number | null
          gold_change_pct?: number | null
          gold_market_time?: string | null
          gold_name?: string | null
          gold_open_interest?: string | null
          gold_price?: number | null
          gold_symbol?: string | null
          gold_volume?: string | null
          id?: string
          nas_change?: number | null
          nas_change_pct?: number | null
          nas_market_time?: string | null
          nas_name?: string | null
          nas_open_interest?: string | null
          nas_price?: number | null
          nas_symbol?: string | null
          nas_volume?: string | null
          raw_gemini_response?: Json | null
          screenshot_url?: string | null
          silver_change?: number | null
          silver_change_pct?: number | null
          silver_market_time?: string | null
          silver_name?: string | null
          silver_open_interest?: string | null
          silver_price?: number | null
          silver_symbol?: string | null
          silver_volume?: string | null
          sp500_change?: number | null
          sp500_change_pct?: number | null
          sp500_market_time?: string | null
          sp500_name?: string | null
          sp500_open_interest?: string | null
          sp500_price?: number | null
          sp500_symbol?: string | null
          sp500_volume?: string | null
          tnote10_change?: number | null
          tnote10_change_pct?: number | null
          tnote10_market_time?: string | null
          tnote10_name?: string | null
          tnote10_open_interest?: string | null
          tnote10_price?: number | null
          tnote10_symbol?: string | null
          tnote10_volume?: string | null
          tnote2_change?: number | null
          tnote2_change_pct?: number | null
          tnote2_market_time?: string | null
          tnote2_name?: string | null
          tnote2_open_interest?: string | null
          tnote2_price?: number | null
          tnote2_symbol?: string | null
          tnote2_volume?: string | null
          tnote5_change?: number | null
          tnote5_change_pct?: number | null
          tnote5_market_time?: string | null
          tnote5_name?: string | null
          tnote5_open_interest?: string | null
          tnote5_price?: number | null
          tnote5_symbol?: string | null
          tnote5_volume?: string | null
        }
        Update: {
          captured_at?: string
          created_at?: string
          crude_change?: number | null
          crude_change_pct?: number | null
          crude_market_time?: string | null
          crude_name?: string | null
          crude_open_interest?: string | null
          crude_price?: number | null
          crude_symbol?: string | null
          crude_volume?: string | null
          dow_change?: number | null
          dow_change_pct?: number | null
          dow_market_time?: string | null
          dow_name?: string | null
          dow_open_interest?: string | null
          dow_price?: number | null
          dow_symbol?: string | null
          dow_volume?: string | null
          gold_change?: number | null
          gold_change_pct?: number | null
          gold_market_time?: string | null
          gold_name?: string | null
          gold_open_interest?: string | null
          gold_price?: number | null
          gold_symbol?: string | null
          gold_volume?: string | null
          id?: string
          nas_change?: number | null
          nas_change_pct?: number | null
          nas_market_time?: string | null
          nas_name?: string | null
          nas_open_interest?: string | null
          nas_price?: number | null
          nas_symbol?: string | null
          nas_volume?: string | null
          raw_gemini_response?: Json | null
          screenshot_url?: string | null
          silver_change?: number | null
          silver_change_pct?: number | null
          silver_market_time?: string | null
          silver_name?: string | null
          silver_open_interest?: string | null
          silver_price?: number | null
          silver_symbol?: string | null
          silver_volume?: string | null
          sp500_change?: number | null
          sp500_change_pct?: number | null
          sp500_market_time?: string | null
          sp500_name?: string | null
          sp500_open_interest?: string | null
          sp500_price?: number | null
          sp500_symbol?: string | null
          sp500_volume?: string | null
          tnote10_change?: number | null
          tnote10_change_pct?: number | null
          tnote10_market_time?: string | null
          tnote10_name?: string | null
          tnote10_open_interest?: string | null
          tnote10_price?: number | null
          tnote10_symbol?: string | null
          tnote10_volume?: string | null
          tnote2_change?: number | null
          tnote2_change_pct?: number | null
          tnote2_market_time?: string | null
          tnote2_name?: string | null
          tnote2_open_interest?: string | null
          tnote2_price?: number | null
          tnote2_symbol?: string | null
          tnote2_volume?: string | null
          tnote5_change?: number | null
          tnote5_change_pct?: number | null
          tnote5_market_time?: string | null
          tnote5_name?: string | null
          tnote5_open_interest?: string | null
          tnote5_price?: number | null
          tnote5_symbol?: string | null
          tnote5_volume?: string | null
        }
        Relationships: []
      }
      rolling_crypto_news: {
        Row: {
          category: string
          created_at: string
          id: string
          published_at: string
          source: string
          summary: string | null
          ticker: string | null
          title: string
          url: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: string
          published_at: string
          source: string
          summary?: string | null
          ticker?: string | null
          title: string
          url: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: string
          published_at?: string
          source?: string
          summary?: string | null
          ticker?: string | null
          title?: string
          url?: string
        }
        Relationships: []
      }
      rolling_etf_news: {
        Row: {
          category: string
          created_at: string
          id: string
          published_at: string
          source: string
          summary: string | null
          ticker: string | null
          title: string
          url: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: string
          published_at: string
          source: string
          summary?: string | null
          ticker?: string | null
          title: string
          url: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: string
          published_at?: string
          source?: string
          summary?: string | null
          ticker?: string | null
          title?: string
          url?: string
        }
        Relationships: []
      }
      rolling_market_news: {
        Row: {
          category: string
          created_at: string
          id: string
          published_at: string
          source: string
          summary: string | null
          title: string
          url: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: string
          published_at: string
          source: string
          summary?: string | null
          title: string
          url: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: string
          published_at?: string
          source?: string
          summary?: string | null
          title?: string
          url?: string
        }
        Relationships: []
      }
      rolling_stock_news: {
        Row: {
          category: string
          created_at: string
          id: string
          published_at: string
          source: string
          summary: string | null
          ticker: string | null
          title: string
          url: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: string
          published_at: string
          source: string
          summary?: string | null
          ticker?: string | null
          title: string
          url: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: string
          published_at?: string
          source?: string
          summary?: string | null
          ticker?: string | null
          title?: string
          url?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
