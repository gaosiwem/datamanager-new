import ReactDOM from "react-dom";
import React, {Component} from "react";
import {Card, CardContent, CardMedia, Grid} from "@material-ui/core";
import ForwardArrow from "@material-ui/icons/ArrowForward";

class Showcase extends Component {
    constructor(props) {
        super(props);

        this.state = {
            features: JSON.parse(document.getElementById('showcase-items-data').textContent)
        }
    }

    renderCTA(type, text, link, enabled) {
        if (!enabled) {
            return;
        }

        if (type === "primary") {
            return (
                <p><a
                    href={link}
                    style={{
                        backgroundColor: '#70b352',
                        color: '#fff',
                        width: '100%',
                        textDecoration: 'none',
                        display: 'block',
                        padding: '6px 16px',
                        borderRadius: '4px',
                        fontWeight: '700'
                    }}
                >
                    <Grid container>
                        <Grid
                            item xs={9}
                            style={{height: '25px', lineHeight: '25px'}}
                        >{text}</Grid>
                        <Grid
                            item xs={3}
                            style={{height: '25px', lineHeight: '25px', textAlign: 'right'}}
                        >
                            <ForwardArrow/>
                        </Grid>
                    </Grid>
                </a></p>
            )
        } else if (type === "secondary") {
            return (
                <p><a
                    href={link}
                >{text}</a></p>
            )
        }
    }

    render() {
        return (<Grid
            style={{maxWidth: '1300px', margin: 'auto', width: '100%'}}
            container
            spacing={3}
        >
            {this.state.features.map((feature, index) => {
                return (
                    <Grid item xs={12} sm={6} key={index}>
                        <Card
                            style={{display: 'flex', height: '100%'}}
                        >
                            <Grid container>
                                <Grid item xs={12} sm={5}>
                                    <CardMedia
                                        image={feature.thumbnail_url}
                                        style={{width: '100%', height: '100%', minHeight: '160px'}}
                                    />
                                </Grid>
                                <Grid item xs={12} sm={7} style={{margin: 'auto 0'}}>
                                    <CardContent>
                                        <b>{feature.name}</b>
                                        <p>{feature.description}</p>
                                        {this.renderCTA('primary', feature.cta_text_1, feature.cta_link_1, true)}
                                        {this.renderCTA(feature.second_cta_type,
                                            feature.cta_text_2,
                                            feature.cta_link_2,
                                            (feature.cta_text_2 != null && feature.cta_text_2.trim() != ""))}
                                    </CardContent>
                                </Grid>
                            </Grid>
                        </Card>
                    </Grid>
                )
            })}
        </Grid>)
    }
}

function scripts() {
    const parent = document.getElementById('js-initShowcase');
    if (parent) {
        ReactDOM.render(<Showcase/>, parent)
    }
}

export default scripts();
