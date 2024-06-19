import Image from 'react-bootstrap/Image';

function InfoModal() {

    function edit_modal() {
        // Select DOM elements from the existing 'datalayer_info' modal
        const datalayer_info: HTMLElement = document.getElementById('datalayer_info')!;
        const dl_title: HTMLElement = document.getElementById('dl_title')!;
        const dl_description: HTMLElement = document.getElementById('dl_description')!;
        const dl_url: HTMLElement = document.getElementById('dl_url')!;
        const dl_source: HTMLElement = document.getElementById('dl_source')!;

        // Overwrite modal elements
        dl_title.innerHTML = `StatMAGIC Tool`
        dl_description.innerHTML = `
            <span class="label">Description</span>
            <br>
            This is a description. and
        `

        dl_url.innerHTML = ``

        dl_source.innerHTML = `
            <span class="label">Usage</span>
            <br>
            Here is how you use this web application...
            `

        datalayer_info.style.display = "block";
    }

    // Return JSX to render Info button
    return (
      <>
        <Image
            src={"/static/cma/img/information.png"}
            height="24px"
            className={"download_icon"}
            onClick={edit_modal}
            style={{cursor: "pointer"}}>
        </Image>
      </>
    )
}

// Export component so it can be imported elsewhere
export default InfoModal;
