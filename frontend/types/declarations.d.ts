declare module "pdfmake/build/pdfmake" {
  const pdfMake: any;
  export default pdfMake;
}

declare module "pdfmake/build/vfs_fonts" {
  const pdfFonts: any;
  export default pdfFonts;
}

declare module "html-to-pdfmake" {
  function htmlToPdfmake(html: string, options?: any): any;
  export default htmlToPdfmake;
}
