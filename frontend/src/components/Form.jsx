import Header from "../components/header.jsx"
import Footer from "../components/Footer.jsx"

const Form = ({children}) => {

    return(
        <>
        <Header/>
            <div>
                {children}
            </div>
        <Footer/>
        </>
    )
}

export default Form